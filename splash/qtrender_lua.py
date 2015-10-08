# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function
import json
import functools
import resource
import contextlib
import time
import sys
from urllib import urlencode
import twisted

from PyQt4.QtCore import QTimer
import lupa

import splash
from splash.browser_tab import JsError
from splash.lua_runner import (
    BaseScriptRunner,
    ImmediateResult,
    AsyncCommand,
)
from splash.qtrender import RenderScript, stop_on_error
from splash.lua import get_main, get_main_sandboxed, parse_error_message
from splash.har.qt import reply2har, request2har
from splash.render_options import RenderOptions
from splash.utils import truncated, BinaryCapsule, requires_attr
from splash.qtutils import (
    REQUEST_ERRORS_SHORT,
    drop_request,
    set_request_url,
    create_proxy,
    get_versions)
from splash.lua_runtime import SplashLuaRuntime
from splash.exceptions import ScriptError


class AsyncBrowserCommand(AsyncCommand):
    def __repr__(self):
        kwargs = self.kwargs.copy()
        if 'callback' in kwargs:
            kwargs['callback'] = '<a callback>'
        if 'errback' in kwargs:
            kwargs['errback'] = '<an errback>'
        kwargs_repr = truncated(repr(kwargs), 400, "...[long kwargs truncated]")
        return "%s(id=%r, name=%r, kwargs=%s)" % (
            self.__class__.__name__, self.id, self.name, kwargs_repr
        )


def command(async=False, can_raise_async=False, table_argument=False,
            sets_callback=False):
    """ Decorator for marking methods as commands available to Lua """

    if sets_callback:
        table_argument = True

    def decorator(meth):
        meth = detailed_exceptions()(meth)

        if not table_argument:
            meth = lupa.unpacks_lua_table_method(meth)

        if sets_callback:
            meth = first_argument_from_storage(meth)

        meth = exceptions_as_return_values(
            can_raise(
                emits_lua_objects(meth)
            )
        )
        meth._is_command = True
        meth._is_async = async
        meth._can_raise_async = can_raise_async
        meth._sets_callback = sets_callback
        return meth

    return decorator


def lua_property(name):
    """ Decorator for marking methods that make attributes available to Lua """

    def decorator(meth):
        def setter(method):
            meth._setter_method = method.__name__
            return method

        meth._is_lua_property = True
        meth._name = name
        meth.lua_setter = setter
        return meth

    return decorator


def emits_lua_objects(meth):
    """
    This decorator makes method convert results to
    native Lua formats when possible
    """

    @functools.wraps(meth)
    def wrapper(self, *args, **kwargs):
        res = meth(self, *args, **kwargs)
        py2lua = self.lua.python2lua
        if isinstance(res, tuple):
            return tuple(py2lua(r) for r in res)
        else:
            return py2lua(res)

    return wrapper


def first_argument_from_storage(meth):
    """
    Methods decorated with ``first_argument_from_storage`` decorator
    take a value from self.tmp_storage and use it
    as a first argument. It is a workaround for Lupa issue
    (see https://github.com/scoder/lupa/pull/49).
    """

    @functools.wraps(meth)
    def wrapper(self, *args, **kwargs):
        arg = self.tmp_storage[1]
        del self.tmp_storage[1]
        return meth(self, arg, *args, **kwargs)

    return wrapper


def is_command(meth):
    """ Return True if method is an exposed Lua command """
    return getattr(meth, '_is_command', False)


def is_lua_property(meth):
    """ Return True if method is exposed to an Lua attribute """
    return getattr(meth, '_is_lua_property', False)


def can_raise(meth):
    """
    Decorator for preserving Python exception objects raised in Python
    methods called from Lua.
    """

    @functools.wraps(meth)
    def wrapper(self, *args, **kwargs):
        try:
            return meth(self, *args, **kwargs)
        except BaseException as e:
            self._exceptions.append(e)
            raise

    return wrapper


def exceptions_as_return_values(meth):
    """
    Decorator for allowing Python exceptions to be caught from Lua.

    It makes wrapped methods return ``True, result`` and ``False, repr(exception)``
    pairs instead of raising an exception; Lua script should handle it itself
    and raise an error when needed. In Splash this is done by
    splash/lua_modules/splash.lua unwraps_errors decorator.
    """

    @functools.wraps(meth)
    def wrapper(self, *args, **kwargs):
        try:
            result = meth(self, *args, **kwargs)
            if isinstance(result, tuple):
                return (True,) + result
            else:
                return True, result
        except Exception as e:
            return False, repr(e)

    wrapper._returns_error_flag = True
    return wrapper


def detailed_exceptions(method_name=None):
    """
    Add method name and a default error type to the error info.
    """

    def decorator(meth):
        _name = meth.__name__ if method_name is None else method_name

        @functools.wraps(meth)
        def wrapper(self, *args, **kwargs):
            try:
                return meth(self, *args, **kwargs)
            except ScriptError as e:
                info = e.args[0]
                if not isinstance(info, dict):
                    raise
                info.setdefault('type', ScriptError.SPLASH_LUA_ERROR)
                info.setdefault('splash_method', _name)
                raise e

        return wrapper

    return decorator


def get_commands(obj):
    """
    Inspect a Python object and get a dictionary of all its commands
    which was made available to Lua using @command decorator.
    """
    commands = {}
    for name in dir(obj):
        value = getattr(obj, name)
        if is_command(value):
            commands[name] = {
                'is_async': getattr(value, '_is_async'),
                'returns_error_flag': getattr(value, '_returns_error_flag', False),
                'can_raise_async': getattr(value, '_can_raise_async', False),
                'sets_callback': getattr(value, '_sets_callback', False),
            }
    return commands


def get_lua_properties(obj):
    """
    Inspect a Python object and get a dictionary of all lua properties, their
    getter and setter methods which were made available to Lua using
    @lua_property and @<getter_method_name>.lua_setter decorators.
    """
    lua_properties = {}
    for name in dir(obj):
        value = getattr(obj, name)
        if is_lua_property(value):
            setter_method = getattr(value, '_setter_method')
            lua_properties[setter_method] = {
                'name': getattr(value, '_name'),
                'getter_method': name,
            }
    return lua_properties


class _WrappedJavascriptFunction(object):
    """
    JavaScript functions wrapper. It allows to call JS functions
    with arguments.
    """

    def __init__(self, splash, source):
        """
        :param splash.browser_tab.BrowserTab tab: BrowserTab object
        :param str source: function source code
        """
        self.lua = splash.lua
        self.tab = splash.tab
        self.source = source
        self._exceptions = splash._exceptions

    @exceptions_as_return_values
    @can_raise
    @emits_lua_objects
    def __call__(self, *args):
        args = self.lua.lua2python(args)
        args_text = json.dumps(args, ensure_ascii=False, encoding="utf8")[1:-1]
        func_text = json.dumps([self.source], ensure_ascii=False, encoding='utf8')[1:-1]
        wrapper_script = """
        (function(func_text){
            try{
                var func = eval("(" + func_text + ")");
                return {
                    result: func(%(args)s),
                    error: false,
                }
            }
            catch(e){
                return {
                    error: true,
                    errorType: e.name,
                    errorMessage: e.message,
                    errorRepr: e.toString(),
                }
            }
        })(%(func_text)s)
        """ % {"func_text": func_text, "args": args_text}

        # print(wrapper_script)
        res = self.tab.evaljs(wrapper_script)

        if not isinstance(res, dict):
            raise ScriptError({
                'type': ScriptError.UNKNOWN_ERROR,
                'js_error_message': res,
                'message': "unknown error during JS function call: "
                           "{!r}; {!r}".format(res, wrapper_script)
            })

        if res.get("error", False):
            err_message = res.get('errorMessage')
            err_type = res.get('errorType', '<custom JS error>')
            err_repr = res.get('errorRepr', '<unknown JS error>')
            if err_message is None:
                err_message = err_repr
            raise ScriptError({
                'type': ScriptError.JS_ERROR,
                'js_error_type': err_type,
                'js_error_message': err_message,
                'js_error': err_repr,
                'message': "error during JS function call: "
                           "{!r}".format(err_repr)
            })

        return res.get("result")


class BaseExposedObject(object):
    """ Base class for objects exposed to Lua """
    _base_attribute_whitelist = ['commands', 'lua_properties', 'tmp_storage']
    _attribute_whitelist = []

    def __init__(self, lua):
        self.lua = lua
        commands = get_commands(self)
        self.commands = lua.python2lua(commands)

        lua_properties = get_lua_properties(self)
        self.lua_properties = lua.python2lua(lua_properties)

        self.attr_whitelist = (
            list(commands.keys()) +
            list(lua_properties.keys()) +
            [lua_properties[attr]['getter_method'] for attr in lua_properties] +
            self._base_attribute_whitelist +
            self._attribute_whitelist
        )
        lua.add_allowed_object(self, self.attr_whitelist)

        self._exceptions = []
        self.tmp_storage = lua.table_from({})  # a workaround for callbacks

    def clear(self):
        self.lua.remove_allowed_object(self)
        self.lua = None
        # self._exceptions = None
        self.tmp_storage = None
        self.lua_properties = None
        self.commands = None

    @classmethod
    @contextlib.contextmanager
    def wraps(cls, lua, *args, **kwargs):
        """
        Context manager which returns a wrapped object
        suitable for using in Lua code.
        """
        obj = cls(lua, *args, **kwargs)
        try:
            with lua.object_allowed(obj, obj.attr_whitelist):
                yield obj
        finally:
            obj.clear()


class Splash(BaseExposedObject):
    """
    This object is passed to Lua script as an argument to 'main' function
    (wrapped in 'Splash' Lua object; see :file:`splash/lua_modules/splash.lua`).
    """
    _result_content_type = None
    _result_status_code = 200
    _attribute_whitelist = ['args']

    def __init__(self, lua, tab, render_options=None, sandboxed=False):
        """
        :param SplashLuaRuntime lua: Lua wrapper
        :param splash.browser_tab.BrowserTab tab: BrowserTab object
        :param splash.render_options.RenderOptions render_options: arguments
        """
        if isinstance(render_options, RenderOptions):
            self.args = lua.python2lua(render_options.data)
        elif isinstance(render_options, dict):
            self.args = lua.python2lua(render_options)
        elif render_options is None:
            self.args = lua.python2lua({})
        else:
            raise ValueError("Invalid render_options type: %s" % render_options.__class__)

        self.sandboxed = sandboxed
        self.tab = tab
        self._result_headers = []

        super(Splash, self).__init__(lua)

        wrapper = self.lua.eval("require('splash')")
        self._wrapped = wrapper._create(self)

    @lua_property('js_enabled')
    @command()
    def get_js_enabled(self):
        return self.tab.get_js_enabled()

    @get_js_enabled.lua_setter
    @command()
    def set_js_enabled(self, value):
        self.tab.set_js_enabled(value)

    @command(async=True)
    def wait(self, time, cancel_on_redirect=False, cancel_on_error=True):
        time = float(time)
        if time < 0:
            raise ScriptError({
                "argument": "time",
                "message": "splash:wait() time can't be negative",
            })

        def success():
            cmd.return_result(True)

        def redirect(error_info):
            cmd.return_result(None, 'redirect')

        def error(error_info):
            cmd.return_result(None, self._error_info_to_lua(error_info))

        cmd = AsyncBrowserCommand("wait", dict(
            time_ms=time * 1000,
            callback=success,
            onredirect=redirect if cancel_on_redirect else False,
            onerror=error if cancel_on_error else False,
        ))
        return cmd

    @command(async=True)
    def go(self, url, baseurl=None, headers=None, http_method="GET", body=None, formdata=None):

        if url is None:
            raise ScriptError({
                "argument": "url",
                "message": "'url' is required for splash:go",
            })

        http_method = http_method.upper()
        if http_method not in ["POST", "GET"]:
            raise ScriptError({
                "argument": "http_method",
                "message": "Unsupported HTTP method: {}".format(http_method)
            })

        if formdata and body:
            raise ScriptError({
                "argument": "body",
                "message": "formdata and body cannot be passed to go() in one call"
            })

        elif formdata:
            body = self.lua.lua2python(formdata, max_depth=3)
            if isinstance(body, dict):
                body = urlencode(body)
            else:
                raise ScriptError({"argument": "formdata",
                                   "message": "formdata argument for go() must be Lua table"})

        elif body:
            if not isinstance(body, basestring):
                raise ScriptError({"argument": "body",
                                   "message": "request body must be string"})

        if self.tab.web_page.navigation_locked:
            return ImmediateResult((None, "navigation_locked"))

        if http_method == "GET" and body:
            raise ScriptError({"argument": "body",
                               "message": "GET request cannot have body"})

        def success():
            try:
                code = self.tab.last_http_status()
                if code and 400 <= code < 600:
                    # return HTTP errors as errors
                    cmd.return_result(None, "http%d" % code)
                else:
                    cmd.return_result(True)
            except Exception as e:
                cmd.return_result(None, "internal_error")

        def error(error_info):
            cmd.return_result(None, self._error_info_to_lua(error_info))

        cmd = AsyncBrowserCommand("go", dict(
            url=url,
            baseurl=baseurl,
            callback=success,
            errback=error,
            http_method=http_method,
            body=body,
            headers=self.lua.lua2python(headers, max_depth=3)
        ))
        return cmd

    @command()
    def html(self):
        return self.tab.html()

    @command()
    def png(self, width=None, height=None, render_all=False,
            scale_method=None):
        if width is not None:
            width = int(width)
        if height is not None:
            height = int(height)
        result = self.tab.png(width, height, b64=False, render_all=render_all,
                              scale_method=scale_method)
        return BinaryCapsule(result, 'image/png')

    @command()
    def jpeg(self, width=None, height=None, render_all=False,
             scale_method=None, quality=None):
        if width is not None:
            width = int(width)
        if height is not None:
            height = int(height)
        if quality is not None:
            quality = int(quality)
        result = self.tab.jpeg(width, height, b64=False, render_all=render_all,
                               scale_method=scale_method, quality=quality)
        return BinaryCapsule(result, 'image/jpeg')

    @command()
    def har(self, reset=False):
        return self.tab.har(reset=reset)

    @command()
    def har_reset(self):
        self.tab.har_reset()

    @command()
    def history(self):
        return self.tab.history()

    @command()
    def stop(self):
        self.tab.stop_loading()

    @command()
    def evaljs(self, snippet):
        try:
            return self.tab.evaljs(snippet)
        except JsError as e:
            info = e.args[0]
            info['type'] = ScriptError.JS_ERROR
            raise ScriptError(info)

    @command()
    def runjs(self, snippet):
        try:
            self.tab.runjs(snippet)
            return True
        except JsError as e:
            info = e.args[0]
            info['type'] = ScriptError.JS_ERROR
            info['splash_method'] = 'runjs'
            return None, info

    @command(async=True, can_raise_async=True)
    def wait_for_resume(self, snippet, timeout=0):
        def callback(result):
            cmd.return_result(self.lua.python2lua(result))

        def errback(msg, raise_):
            cmd.return_result(None, "JavaScript error: %s" % msg, raise_)

        cmd = AsyncBrowserCommand("wait_for_resume", dict(
            js_source=snippet,
            callback=callback,
            errback=errback,
            timeout=timeout,
        ))
        return cmd

    @command()
    def private_jsfunc(self, func):
        return _WrappedJavascriptFunction(self, func)

    def _http_request(self, url, headers, follow_redirects=True, body=None, browser_command="http_get"):
        if url is None:
            raise ScriptError({
                "argument": "url",
                "message": "'url' is required for splash:{}".format(browser_command)
            })

        def callback(reply):
            reply_har = reply2har(reply, include_content=True, binary_content=True)
            cmd.return_result(self.lua.python2lua(reply_har))

        command_args = dict(
            url=url,
            callback=callback,
            headers=self.lua.lua2python(headers, max_depth=3),
            follow_redirects=follow_redirects
        )
        if browser_command == "http_post":
            command_args.update(dict(body=body))
        cmd = AsyncBrowserCommand(browser_command, command_args)
        return cmd

    @command(async=True)
    def http_get(self, url, headers=None, follow_redirects=True):
        return self._http_request(url, headers, follow_redirects)

    @command(async=True)
    def http_post(self, url, headers=None, follow_redirects=True, body=None):
        """
        :param url: string with url to fetch
        :param headers: dict, if None {"content-type": "application/x-www-form-urlencoded"} will be added later
        :param follow_redirects: boolean
        :param body: string with body to be sent in request
        :return: AysncBrowserCommand http_post
        """
        if body and not isinstance(body, basestring):
            raise ScriptError({"argument": "body",
                               "message": "body argument for splash:http_post() must be string"})

        return self._http_request(url, headers, follow_redirects, body, browser_command="http_post")

    @command(async=True)
    def autoload(self, source_or_url=None, source=None, url=None):
        if len([a for a in [source_or_url, source, url] if a is not None]) != 1:
            raise ScriptError({
                "message": "splash:autoload requires a single argument",
            })

        if source_or_url is not None:
            source_or_url = source_or_url.strip()
            if source_or_url.startswith(("http://", "https://")):
                source, url = None, source_or_url
            else:
                source, url = source_or_url, None

        if source is not None:
            # load source directly
            self.tab.autoload(source)
            return ImmediateResult(True)
        else:
            # load JS from a remote resource
            def callback(reply):
                if reply.error():
                    reason = REQUEST_ERRORS_SHORT.get(reply.error(), '?')
                    cmd.return_result(None, reason)
                else:
                    source = bytes(reply.readAll())
                    self.tab.autoload(source)
                    cmd.return_result(True)

            cmd = AsyncBrowserCommand("http_get", dict(
                url=url,
                callback=callback
            ))
            return cmd

    @command()
    def autoload_reset(self):
        self.tab.autoload_reset()

    @command(async=True)
    def set_content(self, data, mime_type=None, baseurl=None):
        def success():
            cmd.return_result(True)

        def error(error_info):
            cmd.return_result(None, self._error_info_to_lua(error_info))

        cmd = AsyncBrowserCommand("set_content", dict(
            data=data,
            baseurl=baseurl,
            mime_type=mime_type,
            callback=success,
            errback=error,
        ))
        return cmd

    @command()
    def lock_navigation(self):
        self.tab.lock_navigation()

    @command()
    def unlock_navigation(self):
        self.tab.unlock_navigation()

    @command()
    def get_cookies(self):
        return self.tab.get_cookies()

    @command()
    def clear_cookies(self):
        return self.tab.clear_cookies()

    @command(table_argument=True)
    def init_cookies(self, cookies):
        cookies = self.lua.lua2python(cookies, max_depth=3)
        if isinstance(cookies, dict):
            keys = sorted(cookies.keys())
            cookies = [cookies[k] for k in keys]
        return self.tab.init_cookies(cookies)

    @command()
    def delete_cookies(self, name=None, url=None):
        return self.tab.delete_cookies(name=name, url=url)

    @command()
    def add_cookie(self, name, value, path=None, domain=None, expires=None,
                   httpOnly=None, secure=None):
        cookie = dict(name=name, value=value)
        if path is not None:
            cookie["path"] = path
        if domain is not None:
            cookie["domain"] = domain
        if expires is not None:
            cookie["expires"] = expires
        if httpOnly is not None:
            cookie["httpOnly"] = httpOnly
        if secure is not None:
            cookie["secure"] = secure
        return self.tab.add_cookie(cookie)

    @command()
    def set_result_content_type(self, content_type):
        if not isinstance(content_type, basestring):
            raise ScriptError({
                "argument": "content_type",
                "message": "splash:set_result_content_type() argument "
                           "must be a string",
            })
        self._result_content_type = content_type

    @command()
    def set_result_status_code(self, code):
        if not isinstance(code, int) or not (200 <= code <= 999):
            raise ScriptError({
                "argument": "code",
                "message": "splash:set_result_status_code() argument must be "
                           "a number 200 <= code <= 999",
            })
        self._result_status_code = code

    @command()
    def set_result_header(self, name, value):
        if not all([isinstance(h, basestring) for h in [name, value]]):
            raise ScriptError({
                "message": "splash:set_result_header() arguments "
                           "must be strings"
            })

        try:
            name = name.decode('utf-8').encode('ascii')
            value = value.decode('utf-8').encode('ascii')
        except UnicodeEncodeError:
            raise ScriptError({
                "message": "splash:set_result_header() arguments must be ascii"
            })

        header = (name, value)
        self._result_headers.append(header)

    @command()
    def set_user_agent(self, value):
        if not isinstance(value, basestring):
            raise ScriptError({
                "argument": "value",
                "message": "splash:set_user_agent() argument must be a string",
            })
        self.tab.set_user_agent(value)

    @command(table_argument=True)
    def set_custom_headers(self, headers):
        self.tab.set_custom_headers(self.lua.lua2python(headers, max_depth=3))

    @command()
    def get_viewport_size(self):
        sz = self.tab.web_page.viewportSize()
        return sz.width(), sz.height()

    @command()
    def set_viewport_size(self, width, height):
        self.tab.set_viewport('%dx%d' % (width, height))

    @command()
    def set_viewport_full(self):
        return tuple(self.tab.set_viewport('full'))

    @lua_property('images_enabled')
    @command()
    def get_images_enabled(self):
        return self.tab.get_images_enabled()

    @get_images_enabled.lua_setter
    @command()
    def set_images_enabled(self, enabled):
        if enabled is not None:
            self.tab.set_images_enabled(int(enabled))

    @lua_property('resource_timeout')
    @command()
    def get_resource_timeout(self):
        return self.tab.get_resource_timeout()

    @get_resource_timeout.lua_setter
    @command()
    def set_resource_timeout(self, timeout):
        if timeout is None:
            timeout = 0
        timeout = float(timeout)
        if timeout < 0:
            raise ScriptError({
                "message": "splash.resource_timeout can't be negative"
            })
        self.tab.set_resource_timeout(timeout)

    @command()
    def status_code(self):
        return self.tab.last_http_status()

    @command()
    def url(self):
        return self.tab.url

    @command()
    def get_perf_stats(self):
        """ Return performance-related statistics. """
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        # on Mac OS X ru_maxrss is in bytes, on Linux it is in KB
        rss_mul = 1 if sys.platform == 'darwin' else 1024
        return {'maxrss': rusage.ru_maxrss * rss_mul,
                'cputime': rusage.ru_utime + rusage.ru_stime,
                'walltime': time.time()}

    @command(sets_callback=True)
    def private_on_request(self, callback):
        """
        Register a Lua callback to be called when a resource is requested.
        """

        def _callback(request, operation, outgoing_data):
            with _ExposedRequest.wraps(self.lua, request, operation, outgoing_data) as req:
                callback(req)

        self.tab.register_callback("on_request", _callback)
        return True

    @command(sets_callback=True)
    def private_on_response_headers(self, callback):
        def _callback(reply):
            with _ExposedBoundResponse.wraps(self.lua, reply) as resp:
                callback(resp)

        self.tab.register_callback("on_response_headers", _callback)
        return True

    @command(sets_callback=True)
    def private_on_response(self, callback):
        def _callback(reply, har_entry):
            resp = _ExposedResponse(self.lua, reply, har_entry)
            run_coro = self.get_coroutine_run_func(
                "splash:on_response", callback, [resp]
            )
            return run_coro(resp)

        self.tab.register_callback("on_response", _callback)
        return True

    @command(sets_callback=True)
    def private_call_later(self, callback, delay=None):
        if delay is None:
            delay = 0
        if not isinstance(delay, (float, int)):
            raise ScriptError({
                "argument": "delay",
                "message": "splash:call_later delay must be a number",
                "splash_method": "call_later",
            })
        delay = int(float(delay) * 1000)
        if delay < 0:
            raise ScriptError({
                "argument": "delay",
                "message": "splash:call_later delay must be >= 0",
                "splash_method": "call_later",
            })
        if lupa.lua_type(callback) != 'function':
            raise ScriptError({
                "argument": "callback",
                "message": "splash:call_later callback is not a function",
                "splash_method": "call_later",
            })

        qtimer = QTimer(self.tab)
        qtimer.setSingleShot(True)
        timer = _ExposedTimer(self, qtimer)
        run_coro = self.get_coroutine_run_func(
            "splash:call_later", callback, return_error=timer.store_error
        )
        qtimer.timeout.connect(run_coro)
        qtimer.start(delay)
        return timer

    @command()
    def on_response_reset(self):
        self.tab.clear_callbacks("on_response")

    @command()
    def on_request_reset(self):
        self.tab.clear_callbacks("on_request")

    @command()
    def on_response_headers_reset(self):
        self.tab.clear_callbacks("on_response_headers")

    @command()
    def get_version(self):
        versions = get_versions()
        versions.update({
            "splash": splash.__version__,
            "major": int(splash.version_info[0]),
            "minor": int(splash.version_info[1]),
            "twisted": twisted.version.short(),
            "python": sys.version,
        })
        return versions

    def _error_info_to_lua(self, error_info):
        if error_info is None:
            return "error"
        res = "%s%s" % (error_info.type.lower(), error_info.code)
        if res == "http200":
            return "render_error"
        return res

    def get_real_exception(self):
        if self._exceptions:
            return self._exceptions[-1]

    def clear_exceptions(self):
        self._exceptions[:] = []

    def result_content_type(self):
        if self._result_content_type is None:
            return None
        return str(self._result_content_type)

    def result_status_code(self):
        return self._result_status_code

    def result_headers(self):
        return self._result_headers

    def get_wrapped(self):
        """ Return a Lua wrapper for this object. """
        return self._wrapped

    def run_async_command(self, cmd):
        """ Execute _AsyncBrowserCommand """
        meth = getattr(self.tab, cmd.name)
        return meth(**cmd.kwargs)

    def get_coroutine_run_func(self, name, callback,
                               return_result=None, return_error=None):
        """
        Return a function which runs as coroutine and can be used
        instead of `callback`.
        """

        def func(*coro_args):
            def log(message, min_level=None):
                self.tab.logger.log("[%s] %s" % (name, message), min_level)

            runner = SplashCoroutineRunner(self.lua, self, log, False)
            coro = self.lua.create_coroutine(callback)
            runner.start(coro, coro_args, return_result, return_error)

        return func


class _ExposedTimer(BaseExposedObject):
    """
    Timer object returned by splash:call_later().
    """

    def __init__(self, splash, timer):
        self.timer = timer
        self.errors = []
        super(_ExposedTimer, self).__init__(splash.lua)

        # FIXME: this is a hack.
        # timer is used outside call_later callbacks, so errors
        # are reported as main Splash errors.
        self._exceptions = splash._exceptions

    @command()
    def cancel(self):
        self.timer.stop()

    @command()
    def is_pending(self):
        return self.timer.isActive()

    @command()
    def reraise(self):
        if self.errors:
            ex = self.errors[-1]
            if isinstance(ex, ScriptError):
                info = ex.args[0]
                info['splash_method'] = None
                info['timer_method'] = 'reraise'
            raise ex

    def store_error(self, error):
        self.errors.append(error)


requires_request = requires_attr(
    "request",
    lambda self, meth, attr_name: self._on_request_required(meth, attr_name)
)
requires_response = requires_attr(
    "response",
    lambda self, meth, attr_name: self._on_response_required(meth, attr_name)
)


class _ExposedRequest(BaseExposedObject):
    """ QNetworkRequest wrapper for Lua """
    _attribute_whitelist = ['info']

    def __init__(self, lua, request, operation, outgoing_data):
        super(_ExposedRequest, self).__init__(lua)
        self.request = request
        self.info = self.lua.python2lua(
            request2har(request, operation, outgoing_data)
        )

    def clear(self):
        super(_ExposedRequest, self).clear()
        self.request = None

    def _on_request_required(self, meth, attr_name):
        raise ScriptError({
            "message": "request is used outside a callback",
            "type": ScriptError.SPLASH_LUA_ERROR,
            "splash_method": None,
            "response_method": meth.__name__,
        })

    @command()
    @requires_request
    def abort(self):
        drop_request(self.request)

    @command()
    @requires_request
    def set_url(self, url):
        set_request_url(self.request, url)

    @command()
    @requires_request
    def set_proxy(self, host, port, username=None, password=None, type='HTTP'):
        proxy = create_proxy(host, port, username, password, type)
        self.request.custom_proxy = proxy

    @command()
    @requires_request
    def set_header(self, name, value):
        self.request.setRawHeader(name, value)

    @command()
    @requires_request
    def set_timeout(self, timeout):
        timeout = float(timeout)
        if timeout < 0:
            raise ScriptError({
                "argument": "timeout",
                "splash_method": "on_request",
                "request_method": "set_timeout",
                "message": "request:set_timeout() argument can't be < 0"
            })
        self.request.timeout = timeout


class _ExposedResponse(BaseExposedObject):
    """ Response object exposed to Lua in on_response callback """
    _attribute_whitelist = ["headers", "info", "request"]

    def __init__(self, lua, reply, har_entry=None):
        super(_ExposedResponse, self).__init__(lua)
        # according to specs HTTP response headers should not contain unicode
        # https://github.com/kennethreitz/requests/issues/1926#issuecomment-35524028
        _headers = {str(k): str(v) for k, v in reply.rawHeaderPairs()}
        self.headers = self.lua.python2lua(_headers)
        if har_entry is None:
            resp_info = reply2har(reply)
        else:
            resp_info = har_entry['response']
        self.info = self.lua.python2lua(resp_info)
        self.request = self.lua.python2lua(
            request2har(reply.request(), reply.operation())
        )

    def clear(self):
        super(_ExposedResponse, self).clear()
        self.request = None

    def _on_response_required(self, meth, attr_name):
        raise ScriptError({
            "message": "response is used outside a callback",
            "type": ScriptError.SPLASH_LUA_ERROR,
            "splash_method": None,
            "response_method": meth.__name__,
        })


class _ExposedBoundResponse(_ExposedResponse):
    """ Response object exposed to Lua in on_response_headers callback. """

    def __init__(self, lua, reply, har_entry=None):
        super(_ExposedBoundResponse, self).__init__(lua, reply, har_entry)
        self.response = reply

    def clear(self):
        super(_ExposedBoundResponse, self).clear()
        self.response = None

    @command()
    @requires_response
    def abort(self):
        self.response.abort()


class SplashCoroutineRunner(BaseScriptRunner):
    """
    Utility class for running Splash async functions (e.g. callbacks).
    """

    def __init__(self, lua, splash, log, sandboxed):
        self.splash = splash
        super(SplashCoroutineRunner, self).__init__(lua=lua, log=log, sandboxed=sandboxed)

    def start(self, coro_func, coro_args=None, return_result=None, return_error=None):
        do_nothing = lambda *args, **kwargs: None
        self.return_result = return_result or do_nothing
        self.return_error = return_error or do_nothing
        super(SplashCoroutineRunner, self).start(coro_func, coro_args)

    def on_result(self, result):
        self.return_result(result)

    def on_async_command(self, cmd):
        self.splash.run_async_command(cmd)

    @stop_on_error
    def dispatch(self, cmd_id, *args):
        super(SplashCoroutineRunner, self).dispatch(cmd_id, *args)


class MainCoroutineRunner(SplashCoroutineRunner):
    """
    Utility class for running main Splash Lua coroutine.
    """

    def start(self, main_coro, return_result=None, return_error=None):
        self.splash.clear_exceptions()
        args = [self.splash.get_wrapped()]
        super(MainCoroutineRunner, self).start(main_coro, args, return_result, return_error)

    def on_result(self, result):
        self.return_result((
            result,
            self.splash.result_content_type(),
            self.splash.result_headers(),
            self.splash.result_status_code(),
        ))

    def on_lua_error(self, lua_exception):
        py_exception = self.splash.get_real_exception()

        if not py_exception:
            return

        py_exception = self._make_script_error(py_exception)
        self.log("[lua] LuaError is caused by %r" % py_exception)

        if not isinstance(py_exception, ScriptError):
            # XXX: we only know how to handle ScriptError
            self.log("[lua] returning Lua error as-is")
            return

        # Remove internal details from the Lua error message
        # and add cleaned up information to the error info.
        py_info = py_exception.args[0]
        lua_info = parse_error_message(lua_exception.args[0])
        if isinstance(py_info, dict) and 'message' in py_info:
            py_info.update(lua_info)
            py_info['error'] = py_info['message']  # replace Lua error message
            if 'line_number' in lua_info and 'source' in lua_info:
                py_info['message'] = "%s:%s: %s" % (
                    lua_info['source'], lua_info['line_number'],
                    py_info['error']
                )
            else:
                py_info['message'] = py_info['error']

        raise ScriptError(py_info)

    def _make_script_error(self, ex):
        if not isinstance(ex, (TypeError, ValueError)):
            return ex

        return ScriptError({
            'type': ScriptError.SPLASH_LUA_ERROR,
            'message': ex.args[0],
        })


class LuaRender(RenderScript):
    default_min_log_level = 2

    @stop_on_error
    def start(self, lua_source, sandboxed, lua_package_path,
              lua_sandbox_allowed_modules):
        self.log(lua_source)
        self.sandboxed = sandboxed
        self.lua = SplashLuaRuntime(
            sandboxed=sandboxed,
            lua_package_path=lua_package_path,
            lua_sandbox_allowed_modules=lua_sandbox_allowed_modules
        )
        self.splash = Splash(self.lua, self.tab, self.render_options)

        self.runner = MainCoroutineRunner(
            lua=self.lua,
            splash=self.splash,
            log=self.log,
            sandboxed=sandboxed,
        )

        try:
            main_coro = self.get_main_coro(lua_source)
        except lupa.LuaSyntaxError as e:
            # XXX: is this code active?
            # It looks like we're always getting LuaError
            # because of sandbox and coroutine handling code.
            raise ScriptError({
                'type': ScriptError.SYNTAX_ERROR,
                'message': e.args[0],
            })
        except lupa.LuaError as e:
            # Error happened before starting coroutine
            info = parse_error_message(e.args[0])
            info.update({
                "type": ScriptError.LUA_INIT_ERROR,
                "message": e.args[0],
            })
            raise ScriptError(info)
        # except ValueError as e:
        #     # XXX: when does it happen?
        #     raise ScriptError({
        #         "type": ScriptError.UNKNOWN_ERROR,
        #         "message": repr(e),
        #     })

        self.runner.start(
            main_coro=main_coro,
            return_result=self.return_result,
            return_error=self.return_error,
        )

    def get_main_coro(self, lua_source):
        if self.sandboxed:
            main, env = get_main_sandboxed(self.lua, lua_source)
        else:
            main, env = get_main(self.lua, lua_source)
        return self.lua.create_coroutine(main)

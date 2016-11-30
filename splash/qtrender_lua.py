# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function
import json
import base64
import functools
import resource
import contextlib
import time
import sys
import weakref

import six

import twisted
from PyQt5.QtCore import QTimer
import lupa

import splash
from splash.browser_tab import BrowserTab, JsError
from splash.lua_runner import (
    BaseScriptRunner,
    AsyncCommand,
)
from splash.qtrender import RenderScript, stop_on_error
from splash.lua import (get_main, get_main_sandboxed, parse_error_message,
                        PyResult, _mark_table_as_array)
from splash.har.qt import reply2har, request2har
from splash.har.utils import get_response_body_bytes
from splash.render_options import RenderOptions
from splash.utils import (
    truncated,
    BinaryCapsule,
    to_bytes,
    requires_attr,
    SplashJSONEncoder,
    to_unicode,
    ensure_tuple,
    traverse_data)
from splash.jsutils import escape_js
from splash.qtutils import (
    REQUEST_ERRORS_SHORT,
    drop_request,
    set_request_url,
    create_proxy,
    get_versions,
    get_headers_dict)
from splash.lua_runtime import SplashLuaRuntime
from splash.exceptions import ScriptError, DOMError
from splash.html_element import HTMLElement, escape_js_args


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


class AsyncFunctionCommand(AsyncCommand):
    pass


class StoredExceptions(object):
    def __init__(self):
        self._exceptions = []

    def append(self, ex):
        self._exceptions.append(ex)

    def clear(self):
        self._exceptions[:] = []

    def get_last(self):
        if self._exceptions:
            return self._exceptions[-1]


def rename(name):
    def decorator(meth):
        meth.__name__ = name
        return meth

    return decorator


def command(table_argument=False, sets_callback=False,
            decode_arguments=True, error_as_flag=False, result_as_flag=False):
    """ Decorator for marking methods as commands available to Lua """

    if sets_callback:
        table_argument = True

    def decorator(meth):
        # input arguments processing:
        # args | unpack_table | use_storage | decode
        if decode_arguments:
            meth = decodes_lua_arguments('utf8')(meth)

        if sets_callback:
            meth = first_argument_from_storage(meth)

        if not table_argument:
            meth = lupa.unpacks_lua_table_method(meth)

        # result processing:
        # result | enrich_exception | ex2retval | store_pyex | to_lua
        meth = detailed_exceptions()(meth)

        meth = exceptions_as_return_values(
            can_raise(
                emits_lua_objects(meth)
            ),
            error_as_flag,
            result_as_flag
        )
        meth._is_command = True
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
    def emits_lua_objects_wrapper(self, *args, **kwargs):
        res = meth(self, *args, **kwargs)
        if isinstance(res, PyResult):
            res.result = tuple(self.lua.python2lua(v) for v in res.result)
            return res
        return self.lua.python2lua(res)

    return emits_lua_objects_wrapper


def decodes_lua_arguments(encoding, strict=True):
    """
    This decorator converts function arguments from Lua to Python.
    """
    l2p_kw = {'encoding': encoding, 'strict': strict}

    def decorator(meth):
        @functools.wraps(meth)
        def decodes_lua_arguments_wrapper(self, *args, **kwargs):
            try:
                args = [
                    self.lua.lua2python(a, **l2p_kw)
                    for a in args
                ]
                kwargs = {
                    self.lua.lua2python(k): self.lua.lua2python(v, **l2p_kw)
                    for (k, v) in kwargs.items()
                }
            except ValueError as e:
                raise ScriptError({
                    'type': ScriptError.SPLASH_LUA_ERROR,
                    'message': e.args[0],
                })
            return meth(self, *args, **kwargs)
        return decodes_lua_arguments_wrapper
    return decorator


def first_argument_from_storage(meth):
    """
    Methods decorated with ``first_argument_from_storage`` decorator
    take a value from self.tmp_storage and use it
    as a first argument. It is a workaround for Lupa issue
    (see https://github.com/scoder/lupa/pull/49).
    """
    @functools.wraps(meth)
    def first_argument_from_storage_wrapper(self, *args, **kwargs):
        arg = self.tmp_storage[1]
        del self.tmp_storage[1]
        return meth(self, arg, *args, **kwargs)

    return first_argument_from_storage_wrapper


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
    def can_raise_wrapper(self, *args, **kwargs):
        try:
            return meth(self, *args, **kwargs)
        except BaseException as e:
            if self.exceptions is None:
                print("Ignoring exception:", e)
            else:
                self.exceptions.append(e)
            raise

    return can_raise_wrapper


def add_flag(tuple, flag):
    new_tuple = tuple[:1] + (flag,) + tuple[1:]
    return new_tuple


def exceptions_as_return_values(meth, error_as_flag=False, result_as_flag=False):
    """Decorator for allowing Python exceptions to be caught from Lua.

    TODO: this decorator is the last one on the way from Python to Lua and thus
    is responsible for converting non-PyResult values to PyResult.  This is
    suboptimal and should be fixed.

    """
    @functools.wraps(meth)
    def exceptions_as_return_values_wrapper(self, *args, **kwargs):
        try:
            res = meth(self, *args, **kwargs)
            if isinstance(res, PyResult):
                res = res.result
            else:
                res = (b'return',) + ensure_tuple(res)
            if error_as_flag and (result_as_flag or res[1] is None or res[1] is False):
                res = add_flag(res, True)
        except Exception as e:
            if error_as_flag and self.FLAG_EXCEPTIONS is not None \
                    and any(isinstance(e, x) for x in self.FLAG_EXCEPTIONS):
                res = (b'return', False, repr(e).encode('utf-8'))
            else:
                res = (b'raise', repr(e).encode('utf-8'))

        return res

    return exceptions_as_return_values_wrapper


def detailed_exceptions(method_name=None):
    """
    Add method name and a default error type to the error info.
    """
    def decorator(meth):
        _name = meth.__name__ if method_name is None else method_name

        @functools.wraps(meth)
        def detailed_exceptions_wrapper(self, *args, **kwargs):
            try:
                return meth(self, *args, **kwargs)
            except ScriptError as e:
                info = e.args[0]
                if not isinstance(info, dict):
                    raise
                info.setdefault('type', ScriptError.SPLASH_LUA_ERROR)
                info.setdefault('splash_method', _name)
                raise e

        return detailed_exceptions_wrapper

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
    for attr_name in dir(obj):
        value = getattr(obj, attr_name)
        if is_lua_property(value):
            property_name = getattr(value, '_name')

            lua_properties[property_name] = {
                'getter': attr_name,
                'setter': getattr(value, '_setter_method', None),
            }
    return lua_properties


def unwraps_html_element_arguments(meth):
    """
    Decorator for creating HTMLElements from tables with Element metatable.
    """
    @functools.wraps(meth)
    def wrapper(self, *args, **kwargs):
        def unwrap_all(obj):
            def _unexpose(o):
                unwrapped = o.unwrapped(o, self.lua)
                if isinstance(unwrapped, _ExposedElement):
                    return unwrapped.element
                return o
            return traverse_data(obj, is_wrapped_exposed_object, _unexpose)
        return meth(self, *unwrap_all(args), **unwrap_all(kwargs))
    return wrapper


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
        self.source = escape_js(source)
        self.exceptions = splash.exceptions
        self.splash = splash

    @exceptions_as_return_values
    @can_raise
    @emits_lua_objects
    @unwraps_html_element_arguments
    @decodes_lua_arguments('utf8')
    def __call__(self, *args):
        expr = "eval('('+{func_text}+')')({args})".format(
            func_text=self.source,
            args=escape_js_args(*args)
        )
        try:
            res = self.tab.evaljs(expr)
        except JsError as e:
            raise ScriptError({
                'type': ScriptError.JS_ERROR,
                'js_error_type': e.args[0]['js_error_type'],
                'js_error_message': e.args[0]['js_error_message'],
                'js_error': e.args[0]['js_error'],
                'message': "error during JS function call: "
                           "{!r}".format(e.args[0]['js_error'])
            })

        return self.splash.expose_html_elements(res)


class BaseExposedObject(object):
    """ Base class for objects exposed to Lua """
    _base_attribute_whitelist = ['commands', 'lua_properties', 'tmp_storage',
                                 'is_exposed', 'unwrapped']
    _attribute_whitelist = []
    is_exposed = True

    def __init__(self, lua, exceptions):
        # type: (SplashLuaRuntime, StoredExceptions) -> None
        self.lua = lua
        commands = get_commands(self)
        self.commands = lua.python2lua(commands)

        lua_properties = get_lua_properties(self)
        self.lua_properties = lua.python2lua(lua_properties)

        self.attr_whitelist = (
            list(commands.keys()) +
            [lua_properties[attr]['getter'] for attr in lua_properties] +
            [lua_properties[attr]['setter'] for attr in lua_properties] +
            self._base_attribute_whitelist +
            self._attribute_whitelist
        )
        lua.add_allowed_object(self, self.attr_whitelist)

        self.exceptions = exceptions
        self.tmp_storage = lua.table_from({})  # a workaround for callbacks
        self.destroyed = False

    def clear(self):
        self.lua.remove_allowed_object(self)
        self.lua = None
        self.tmp_storage = None
        self.lua_properties = None
        self.commands = None
        self.exceptions = None
        self.destroyed = True

    @contextlib.contextmanager
    def allowed(self):
        """
        Context manager which makes it possible to use a wrapped object
        in Lua code and cleans it in the end.
        """
        try:
            with self.lua.object_allowed(self, self.attr_whitelist):
                yield self
        finally:
            self.clear()

    @command(decode_arguments=False)
    def unwrapped(self, lua):
        """
        Return self, but only if a caller is able to provide SplashScriptRunner
        object this object is created with.

        This method is internal, it shouldn't be called from Lua code.
        """
        if lua is self.lua:
            return PyResult(self)


def is_wrapped_exposed_object(obj):
    """
    Return True if ``obj`` is a Lua (lupa) wrapper for a BaseExposedObject
    instance
    """
    if not hasattr(obj, 'is_object') or not callable(obj.is_object):
        return False
    return bool(obj.is_object())


class Splash(BaseExposedObject):
    """
    This object is passed to Lua script as an argument to 'main' function
    (wrapped in 'Splash' Lua object; see :file:`splash/lua_modules/splash.lua`).
    """
    _result_content_type = None
    _result_status_code = 200
    _attribute_whitelist = ['args']

    def __init__(self, lua, exceptions, tab, render_options=None, log=None):
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
            raise TypeError("Invalid render_options type: %s" %
                            render_options.__class__)

        self.tab = tab  # type: BrowserTab
        self.log = log or tab.logger.log
        self._result_headers = []
        self._objects_to_clear = weakref.WeakSet()

        super(Splash, self).__init__(lua, exceptions)

        wrapper = self.lua.eval("require('splash')")
        self._wrapped = wrapper._create(self)
        self.request_wrapper = self.lua.eval("require('request')")
        self.response_wrapper = self.lua.eval("require('response')")
        self.element_wrapper = self.lua.eval("require('element')")

    def clear(self):
        self.log("[splash] clearing %d objects" % len(self._objects_to_clear),
                 min_level=2)
        for obj in self._objects_to_clear:
            try:
                obj.clear()
            except Exception as e:
                print(e)
        super(Splash, self).clear()

    @lua_property('js_enabled')
    @command()
    def get_js_enabled(self):
        return self.tab.get_js_enabled()

    @get_js_enabled.lua_setter
    @command()
    def set_js_enabled(self, value):
        self.tab.set_js_enabled(value)

    @lua_property("private_mode_enabled")
    @command()
    def get_private_mode_enabled(self):
        return self.tab.get_private_mode_enabled()

    @get_private_mode_enabled.lua_setter
    @command()
    def set_private_mode_enabled(self, value):
        self.tab.set_private_mode_enabled(bool(value))

    @lua_property('response_body_enabled')
    @command()
    def get_response_body_enabled(self):
        return self.tab.get_response_body_enabled()

    @get_response_body_enabled.lua_setter
    @command()
    def set_response_body_enabled(self, value):
        self.tab.set_response_body_enabled(bool(value))

    @command()
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
        return PyResult.yield_(cmd)

    @command(sets_callback=True, decode_arguments=False)
    def with_timeout(self, func, timeout):
        if timeout is None:
            ScriptError({
                "argument": "timeout",
                "message": "splash:with_timeout timeout must be specified",
                "splash_method": "with_timeout",
            })
        if not isinstance(timeout, (float, int)):
            raise ScriptError({
                "argument": "timeout",
                "message": "splash:with_timeout timeout must be a number",
                "splash_method": "with_timeout",
            })

        timeout = int(float(timeout) * 1000)

        if timeout < 0:
            raise ScriptError({
                "argument": "timeout",
                "message": "splash:with_timeout timeout must be >= 0",
                "splash_method": "with_timeout",
            })

        if lupa.lua_type(func) != 'function':
            raise ScriptError({
                "argument": "func",
                "message": "splash:with_timeout func is not a function",
                "splash_method": "with_timeout",
            })

        qtimer = QTimer(self.tab)
        qtimer.setSingleShot(True)

        def timer_callback():
            run_coro.runner.stop()
            cmd.return_result(None, 'timeout_over')

        qtimer.timeout.connect(timer_callback)

        def coro_success(result):
            if not qtimer.isActive():
                return

            qtimer.stop()
            cmd.return_result(True, *ensure_tuple(result))

        def coro_error(ex):
            if not qtimer.isActive():  # pragma: no cover
                raise AssertionError("Should not happen")

            qtimer.stop()

            info = str(ex.args[0]["error"])
            cmd.return_result(None, info)

        run_coro = self.get_coroutine_run_func(
            "splash:with_timeout", func, coro_success, coro_error)

        def start():
            qtimer.start(timeout)
            run_coro.runner = run_coro()

        cmd = AsyncFunctionCommand("with_timeout", dict(
            func=start
        ))

        return PyResult.yield_(cmd)

    @command(decode_arguments=False)
    def go(self, url, baseurl=None, headers=None, http_method="GET", body=None,
           formdata=None):
        url = self.lua.lua2python(url, max_depth=1)
        baseurl = self.lua.lua2python(baseurl, max_depth=1)
        headers = self.lua.lua2python(headers, max_depth=2, encoding=None)
        http_method = self.lua.lua2python(http_method, max_depth=1)
        formdata = self.lua.lua2python(formdata, max_depth=3)

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
            # XXX: should it be binary or unicode?
            body = self.lua.lua2python(formdata, max_depth=3, encoding=None)
            if isinstance(body, dict):
                body = six.moves.urllib.parse.urlencode(body)
            else:
                raise ScriptError({
                    "argument": "formdata",
                    "message": "formdata argument for go() must be a Lua table"
                })

        elif body:
            body = self.lua.lua2python(body, encoding=None, max_depth=2)
            if not isinstance(body, bytes):
                raise ScriptError({"argument": "body",
                                   "message": "request body must be a string"})

        if http_method == "GET" and body:
            raise ScriptError({"argument": "body",
                               "message": "GET request cannot have body"})

        if self.tab.web_page.navigation_locked:
            return None, 'navigation_locked'

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
            headers=headers,
        ))
        return PyResult.yield_(cmd)

    @command()
    def html(self):
        return self.tab.html()

    @command()
    def png(self, width=None, height=None, render_all=False,
            scale_method=None, region=None):
        if width is not None:
            width = int(width)
        if height is not None:
            height = int(height)
        region = self.validate_region(region)
        result = self.tab.png(width, height, b64=False, render_all=render_all,
                              scale_method=scale_method, region=region)
        if not result:
            return None
        return BinaryCapsule(result, 'image/png')

    @command()
    def jpeg(self, width=None, height=None, render_all=False,
             scale_method=None, quality=None, region=None):
        if width is not None:
            width = int(width)
        if height is not None:
            height = int(height)
        if quality is not None:
            quality = int(quality)

        region = self.validate_region(region)
        result = self.tab.jpeg(width, height, b64=False, render_all=render_all,
                               scale_method=scale_method, quality=quality,
                               region=region)
        if not result:
            return None
        return BinaryCapsule(result, 'image/jpeg')

    @staticmethod
    def validate_region(region, var_name="region"):
        if region is not None:
            try:
                if isinstance(region, dict):
                    region = [region[i] for i in range(1, 5)]
                region = tuple(int(region[i]) for i in range(4))
            except Exception:
                raise ScriptError("%s must be a table containing 4 numbers"
                                  " {left, top, right, bottom} " % var_name)
        return region

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
            res = self.tab.evaljs(snippet)
            return self.expose_html_elements(res)
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

    @command()
    def wait_for_resume(self, snippet, timeout=0):
        def callback(result):
            assert result is not None
            cmd.return_result(result)

        def errback(msg, raise_):
            errmsg = "JavaScript error: %s" % msg
            if raise_:
                cmd.raise_error(errmsg)
            else:
                cmd.return_result(None, errmsg)

        cmd = AsyncBrowserCommand("wait_for_resume", dict(
            js_source=snippet,
            callback=callback,
            errback=errback,
            timeout=timeout,
        ))
        return PyResult.yield_(cmd)

    @command()
    def _jsfunc(self, func):
        return _WrappedJavascriptFunction(self, func)

    def _http_request(self, url, headers, follow_redirects=True, body=None,
                      browser_command="http_get"):
        if url is None:
            msg = "'url' is required for splash:{}".format(browser_command)
            raise ScriptError({"argument": "url", "message": msg})

        def callback(reply):
            content = bytes(reply.readAll())
            req = _ExposedRequest.from_reply(self.lua, self.exceptions, reply)
            resp = _ExposedResponse(self.lua, self.exceptions, reply, req,
                                    content=content)
            self._objects_to_clear.add(req)
            self._objects_to_clear.add(resp)
            resp_wrapped = self.response_wrapper._create(resp)
            cmd.return_result(resp_wrapped)

        command_args = dict(
            url=url,
            callback=callback,
            headers=self.lua.lua2python(headers, max_depth=3),
            follow_redirects=follow_redirects
        )
        if browser_command == "http_post":
            command_args.update(dict(body=body))
        cmd = AsyncBrowserCommand(browser_command, command_args)
        return PyResult.yield_(cmd)

    @command()
    def http_get(self, url, headers=None, follow_redirects=True):
        return self._http_request(url, headers, follow_redirects)

    @command()
    def http_post(self, url, headers=None, follow_redirects=True, body=None):
        """
        :param url: string with url to fetch
        :param headers: dict, if None then
            {"content-type": "application/x-www-form-urlencoded"} is added.
        :param follow_redirects: boolean
        :param body: string with body to be sent in request
        :return: AysncBrowserCommand http_post
        """
        if isinstance(body, BinaryCapsule):
            body = body.data

        if body and not isinstance(body, (six.text_type, bytes)):
            raise ScriptError({
                "argument": "body",
                "message": "body argument for splash:http_post() must be string"
            })

        return self._http_request(url, headers, follow_redirects, body, browser_command="http_post")

    @command()
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
            return True
        else:
            # load JS from a remote resource
            def callback(reply):
                if reply.error():
                    reason = REQUEST_ERRORS_SHORT.get(reply.error(), '?')
                    cmd.return_result(None, reason)
                else:
                    source = bytes(reply.readAll()).decode('utf-8')
                    self.tab.autoload(source)
                    cmd.return_result(True)

            cmd = AsyncBrowserCommand("http_get", dict(
                url=url,
                callback=callback
            ))
            return PyResult.yield_(cmd)

    @command()
    def autoload_reset(self):
        self.tab.autoload_reset()

    def _check_mouse_coordinates(self, x, y):
        def _assert_number(value, name):
            if not isinstance(value, (int, float)):
                raise ScriptError({
                    "argument": name,
                    "message": "splash mouse event {} coordinate must be "
                               "a number ".format(name)
                })
        _assert_number(x, "x")
        _assert_number(y, "y")

    @command()
    def mouse_click(self, x, y):
        self._check_mouse_coordinates(x, y)
        self.tab.mouse_click(x, y)

    @command()
    def mouse_press(self, x, y):
        self._check_mouse_coordinates(x, y)
        self.tab.mouse_press(x, y)

    @command()
    def mouse_release(self, x, y):
        self._check_mouse_coordinates(x, y)
        self.tab.mouse_release(x, y)

    @command()
    def mouse_hover(self, x, y):
        self._check_mouse_coordinates(x, y)
        self.tab.mouse_hover(x, y)

    @command()
    def send_keys(self, text):
        self.tab.send_keys(text)

    @command()
    def send_text(self, text):
        self.tab.send_text(text)

    @command()
    def set_content(self, data, mime_type=None, baseurl=None):
        if isinstance(data, six.text_type):
            data = data.encode('utf8')

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
        return PyResult.yield_(cmd)

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
        if not isinstance(content_type, six.string_types):
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
        if not all([isinstance(h, six.string_types) for h in [name, value]]):
            raise ScriptError({
                "message": "splash:set_result_header() arguments "
                           "must be strings",
            })

        try:
            name = name.encode('ascii')
            value = value.encode('ascii')
        except UnicodeEncodeError:
            raise ScriptError({
                "message": "splash:set_result_header() arguments must be ascii"
            })

        header = (name, value)
        self._result_headers.append(header)

    @command()
    def set_user_agent(self, value):
        if not isinstance(value, six.string_types):
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

    @lua_property('plugins_enabled')
    @command()
    def get_plugins_enabled(self):
        return self.tab.get_plugins_enabled()

    @get_plugins_enabled.lua_setter
    @command()
    def set_plugins_enabled(self, enabled):
        self.tab.set_plugins_enabled(bool(enabled))

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

    @command(sets_callback=True, decode_arguments=False)
    def _on_request(self, callback):
        """
        Register a Lua callback to be called when a resource is requested.
        """
        def _callback(request, operation, outgoing_data):
            if self.destroyed:
                return
            exceptions = StoredExceptions()  # FIXME: exceptions are discarded
            req = _ExposedBoundRequest(self.lua, exceptions, request, operation,
                                       outgoing_data)
            with req.allowed():
                callback(req)

        self.tab.register_callback("on_request", _callback)
        return True

    @command(sets_callback=True, decode_arguments=False)
    def _on_response_headers(self, callback):
        def _callback(reply):
            if self.destroyed:
                return
            exceptions = StoredExceptions()  # FIXME: exceptions are discarded
            req = _ExposedRequest.from_reply(self.lua, exceptions, reply)
            resp = _ExposedBoundResponse(self.lua, exceptions, reply, req)
            with resp.allowed(), req.allowed():
                callback(resp)

        self.tab.register_callback("on_response_headers", _callback)
        return True

    @command(sets_callback=True, decode_arguments=False)
    def _on_response(self, callback):
        def _callback(reply, har_entry, content):
            if self.destroyed:
                return
            exceptions = StoredExceptions()  # FIXME: exceptions are discarded
            req = _ExposedRequest.from_har(self.lua, exceptions,
                                           har_entry['request'])
            resp = _ExposedResponse(self.lua, exceptions, reply, req, har_entry,
                                    content=content)
            self._objects_to_clear.add(req)
            self._objects_to_clear.add(resp)
            run_coro = self.get_coroutine_run_func(
                "splash:on_response", callback,
            )
            return run_coro(resp)

        self.tab.register_callback("on_response", _callback)
        return True

    @command(sets_callback=True, decode_arguments=False)
    def _call_later(self, callback, delay=None):
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

        # timer is used outside call_later callbacks, so errors
        # are reported as main Splash errors.
        timer = _ExposedTimer(self.lua, self.exceptions, qtimer)
        self._objects_to_clear.add(timer)

        run_coro = self.get_coroutine_run_func(
            "splash:call_later", callback, return_error=timer.store_error
        )
        qtimer.timeout.connect(run_coro)
        qtimer.start(delay)
        return timer

    @command()
    def select(self, selector):
        try:
            result = self.tab.select(selector)
            return self.expose_html_elements(result)
        except (JsError, DOMError) as e:
            raise ScriptError({
                "message": "cannot select the specified element " + str(e),
                "type": ScriptError.SPLASH_LUA_ERROR,
                "splash_method": "select",
            })

    @command()
    def select_all(self, selector):
        try:
            result = self.tab.select_all(selector)
            return self.expose_html_elements(result)
        except (JsError, DOMError):
            raise ScriptError({
                "message": "cannot select the specified elements",
                "type": ScriptError.SPLASH_LUA_ERROR,
                "splash_method": "select_all",
            })

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
        """ Execute _AsyncBrowserCommand or _AsyncCallbackCommand """
        if isinstance(cmd, AsyncBrowserCommand):
            meth = getattr(self.tab, cmd.name)
            return meth(**cmd.kwargs)
        elif isinstance(cmd, AsyncFunctionCommand):
            return cmd.kwargs["func"]()

        raise TypeError('Unknown async command type.')

    def get_coroutine_run_func(self, name, callback,
                               return_result=None, return_error=None):
        """
        Return a function which runs as coroutine and can be used
        instead of `callback`.
        """
        def func(*coro_args):
            def log(message, min_level=None):
                self.log("[%s] %s" % (name, message), min_level)

            runner = SplashCoroutineRunner(self.lua, self, log, False)
            coro = self.lua.create_coroutine(callback)
            runner.start(coro, coro_args, return_result, return_error)
            return runner

        return func

    def expose_html_elements(self, obj):
        """ Wrap all HTMLElement instances to _ExposedElement """
        def _expose(o):
            elem = _ExposedElement(self.lua, self.exceptions, self, o)
            self._objects_to_clear.add(elem)
            return self.element_wrapper._create(elem)

        return traverse_data(
            obj,
            lambda o: isinstance(o, HTMLElement),
            convert=_expose,
        )


class _ExposedTimer(BaseExposedObject):
    """
    Timer object returned by splash:call_later().
    """
    def __init__(self, lua, exceptions, timer):
        self.timer = timer
        self.callback_exceptions = []
        super(_ExposedTimer, self).__init__(lua, exceptions)

    @command()
    def cancel(self):
        self._stop_timer()

    def _stop_timer(self):
        print("_stop_timer", self.timer.isActive())
        if self.timer is not None and self.timer.isActive():
            self.timer.stop()

    @command()
    def is_pending(self):
        return self.timer.isActive()

    @command()
    def reraise(self):
        if self.callback_exceptions:
            ex = self.callback_exceptions[-1]
            if isinstance(ex, ScriptError):
                info = ex.args[0]
                info['splash_method'] = None
                info['timer_method'] = 'reraise'
            raise ex

    def store_error(self, error):
        self.callback_exceptions.append(error)

    def clear(self):
        self._stop_timer()
        self.timer.deleteLater()
        self.timer = None
        super(_ExposedTimer, self).clear()


class _ExposedElement(BaseExposedObject):
    FLAG_EXCEPTIONS = [DOMError]
    _attribute_whitelist = ['inner_id']
    HTMLELEMENT_PROPERTIES = [
        ('accessKey', False),
        ('accessKeyLabel', True),
        ('contentEditable', False),
        ('isContentEditable', True),
        ('dataset', True),
        ('dir', False),
        ('draggable', False),
        ('hidden', False),
        ('lang', False),
        ('offsetHeight', True),
        ('offsetLeft', True),
        ('offsetParent', True),
        ('offsetTop', True),
        ('spellcheck', False),
        ('tabIndex', False),
        ('title', False),
        ('translate', False),
    ]
    ELEMENT_PROPERTIES = [
        ('attributes', True), # NamedNodeMap
        ('classList', True), # DOMTokenList
        ('className', False),
        ('clientHeight', True),
        ('clientLeft', True),
        ('clientTop', True),
        ('clientWidth', True),
        ('id', False),
        ('innerHTML', False),
        ('localeName', True),
        ('namespaceURI', True),
        ('nextElementSibling', True),
        ('outerHTML', False),
        ('prefix', True),
        ('previousElementSibling', True),
        ('scrollHeight', True),
        ('scrollLeft', False),
        ('scrollTop', False),
        ('scrollWidth', True),
        ('tabStop', False),
        ('tagName', True),
    ]
    NODE_PROPERTIES = [
        ('baseURI', True),
        ('childNodes', True),
        ('firstChild', True),
        ('lastChild', True),
        ('nextSibling', True),
        ('nodeName', True),
        ('nodeType', True),
        ('nodeValue', False),
        ('ownerDocument', True),
        ('parentNode', True),
        ('parentElement', True),
        ('previousSibling', True),
        ('rootNode', True),
        ('textContent', False),
    ]

    HTMLELEMENT_METHODS = [
        'blur',
        'click',
        'focus'
    ]
    ELEMENT_METHODS = [
        # 'addEventListener',
        # 'dispatchEvent',
        'getAttribute',
        'getAttributeNS',
        'getBoundingClientRect',
        'getClientRects',
        'getElementsByClassName',
        'getElementsByTagName',
        'getElementsByTagNameNS',
        'hasAttribute',
        'hasAttributeNS',
        'hasAttributes',
        'querySelector',
        'querySelectorAll',
        'releasePointerCapture',
        'remove',
        'removeAttribute',
        'removeAttributeNS',
        # 'removeEventListener',
        'requestFullscreen',
        'requestPointerLock',
        'scrollIntoView',
        'setAttribute',
        'setAttributeNS',
        'setPointerCapture'
    ]
    NODE_METHODS = [
        'appendChild',
        'cloneNode',
        'compareDocumentPosition',
        'contains',
        'hasChildNodes',
        'insertBefore',
        'isDefaultNamespace',
        'isEqualNode',
        'isSameNode',
        'lookupPrefix',
        'lookupNamespaceURI',
        'normalize',
        'removeChild',
        'replaceChild'
    ]

    def __init__(self, lua, exceptions, splash, element):
        # type: (SplashLuaRuntime, StoredExceptions, Splash, HTMLElement) -> None
        self.element = element
        self.splash = splash
        self.tab = splash.tab
        self.inner_id = element.id
        self.event_handlers = {}

        super(_ExposedElement, self).__init__(lua, exceptions)

        self.wrapper = self.lua.eval("require('element')")

    def clear(self):
        super(_ExposedElement, self).clear()
        self.wrapper = None
        self.event_handlers = None
        self.splash = None
        self.tab = None
        self.element = None

    @lua_property('inner_id')
    @command()
    def get_inner_id(self):
        return self.inner_id

    @classmethod
    def init_properties(cls):
        available_properties = cls.NODE_PROPERTIES + cls.ELEMENT_PROPERTIES + \
                               cls.HTMLELEMENT_PROPERTIES

        for (property_name, read_only) in available_properties:
            @lua_property(property_name)
            @command()
            @rename('get_' + property_name)
            def get_property(self, property_name=property_name):
                return cls._node_property(self, property_name)

            setattr(cls, 'get_' + property_name, get_property)

            if not read_only:
                @get_property.lua_setter
                @unwraps_html_element_arguments
                @command()
                @rename('set_' + property_name)
                def set_property(self, value, property_name=property_name):
                    return cls._set_node_property(self, property_name, value)

                setattr(cls, 'set_' + property_name, set_property)

    @classmethod
    def init_methods(cls):
        available_methods = cls.NODE_METHODS + cls.ELEMENT_METHODS + \
                            cls.HTMLELEMENT_METHODS

        for method_name in available_methods:
            @unwraps_html_element_arguments
            @command(table_argument=True)
            def call_method(self, *args, method_name=method_name):
                return cls._node_method(self, method_name, *args)

            setattr(cls, method_name, call_method)

    def _node_method(self, method_name, *args):
        result = self.element.node_method(method_name)(*args)
        return self.splash.expose_html_elements(result)

    def _node_property(self, property_name):
        result = self.element.node_property(property_name)
        return self.splash.expose_html_elements(result)

    def _set_node_property(self, property_name, property_value):
        result = self.element.set_node_property(property_name, property_value)
        return self.splash.expose_html_elements(result)

    @command()
    def _get_style(self):
        return _ExposedElementStyle(self.lua, self.exceptions, self.element)

    def _save_event_handler_id(self, event_name, handler, handler_id,
                               is_on_event=False):
        if self.event_handlers.get(event_name, None) is None:
            self.event_handlers[event_name] = {}

        handler_key = "on" if is_on_event else str(handler)
        self.event_handlers[event_name][handler_key] = handler_id

    def _remove_event_handler_id(self, event_name, handler, is_on_event=False):
        if self.event_handlers.get(event_name, None) is None:
            return None

        handler_key = "on" if is_on_event else str(handler)
        handler_id = self.event_handlers[event_name].get(handler_key, None)
        if handler_id is not None:
            del self.event_handlers[event_name][handler_key]
        return handler_id

    @command(decode_arguments=False)
    def _set_event_handler(self, event_name, handler):
        event_name = self.lua.lua2python(event_name)

        if event_name == "":
            raise ScriptError({
                "argument": "event_name",
                "message": "element:set_event_handler event_name must be specified",
                "splash_method": "set_event_handler",
            })

        if handler is None:
            handler_id = self._remove_event_handler_id(event_name, handler, True)
            if handler_id is not None:
                self.element.unset_event_handler(event_name, handler_id)
            return

        if lupa.lua_type(handler) != 'function':
            raise ScriptError({
                "argument": "handler",
                "message": "element:set_event_handler handler is not a function",
                "splash_method": "set_event_handler",
            })

        def cleanup():
            for handler in run_coro.on_call_after:
                handler()

        def log_error(error, event_name=event_name):
            self.splash.log("[element:on%s] error %s" % (event_name, error),
                            min_level=3)
            cleanup()

        def on_handler_call(result=None):
            cleanup()

        def on_handler_call_error(error):
            log_error(error)

        coro = self.splash.get_coroutine_run_func(
            name="element:on" + event_name,
            callback=handler,
            return_result=on_handler_call,
            return_error=on_handler_call_error
        )

        def run_coro(event, coro=coro):
            wrapper = self.lua.eval("require('event')")
            coro(wrapper._create(_ExposedEvent(self.lua, self.exceptions, event)))

        run_coro.on_call_after = []

        handler_id = self.element.set_event_handler(event_name, run_coro)
        self._save_event_handler_id(event_name, handler, handler_id, True)

    @command(decode_arguments=False)
    def addEventListener(self, event_name, handler, options=None):
        event_name = self.lua.lua2python(event_name)

        if event_name == "":
            raise ScriptError({
                "argument": "event_name",
                "message": "element:addEventListener event_name must be specified",
                "splash_method": "addEventListener",
            })

        if lupa.lua_type(handler) != 'function':
            raise ScriptError({
                "argument": "handler",
                "message": "element:addEventListener handler is not a function",
                "splash_method": "addEventListener",
            })

        if options is not None and not isinstance(options, bool) and lupa.lua_type(options) != 'table':
            raise ScriptError({
                "argument": "options",
                "message": "element:addEventListener options must be a boolean or a table",
                "splash_method": "addEventListener",
            })

        options = self.lua.lua2python(options)

        def cleanup():
            for handler in run_coro.on_call_after:
                handler()

        def log_error(error, event_name=event_name):
            self.splash.log("[element:on%s] error %s" % (event_name, error),
                            min_level=3)
            cleanup()

        def on_handler_call(result=None):
            cleanup()

        def on_handler_call_error(error):
            log_error(error)

        coro = self.splash.get_coroutine_run_func(
            name="element:on" + event_name,
            callback=handler,
            return_result=on_handler_call,
            return_error=on_handler_call_error
        )

        def run_coro(event, coro=coro):
            wrapper = self.lua.eval("require('event')")
            exposed_event = _ExposedEvent(self.lua, self.exceptions, event)
            coro(wrapper._create(exposed_event))

        run_coro.on_call_after = []

        handler_id = self.element.add_event_handler(event_name, run_coro, options)
        self._save_event_handler_id(event_name, handler, handler_id)

    @command(decode_arguments=False)
    def removeEventListener(self, event_name, handler):
        event_name = self.lua.lua2python(event_name)

        if event_name == "":
            raise ScriptError({
                "argument": "event_name",
                "message": "element:removeEventListener event_name must be specified",
                "splash_method": "removeEventListener",
            })

        handler_id = self._remove_event_handler_id(event_name, handler)
        if handler_id is not None:
            self.element.remove_event_handler(event_name, handler_id)

    @command()
    def exists(self):
        return self.element.exists()

    @command(error_as_flag=True)
    def mouse_click(self, x=0, y=0):
        if not isinstance(x, (float, int)):
            raise ScriptError({
                "argument": "x",
                "message": "element:mouse_click x coordinate must be a number",
                "splash_method": "mouse_click",
            })

        if not isinstance(y, (float, int)):
            raise ScriptError({
                "argument": "y",
                "message": "element:mouse_click y coordinate must be a number",
                "splash_method": "mouse_click",
            })

        self.element.mouse_click(float(x), float(y))

    @command(error_as_flag=True)
    def mouse_hover(self, x=0, y=0):
        if not isinstance(x, (float, int)):
            raise ScriptError({
                "argument": "x",
                "message": "element:mouse_hover x coordinate must be a number",
                "splash_method": "mouse_hover",
            })

        if not isinstance(y, (float, int)):
            raise ScriptError({
                "argument": "y",
                "message": "element:mouse_hover y coordinate must be a number",
                "splash_method": "mouse_hover",
            })

        self.element.mouse_hover(float(x), float(y))

    @command()
    def styles(self):
        return self.element.styles()

    @command()
    def bounds(self):
        return self.element.bounds()

    @command()
    def png(self, width=None, scale_method=None, pad=None):
        if width is not None:
            width = int(width)

        if pad is not None and isinstance(pad, (int, float)):
            pad = (pad, pad, pad, pad)
        pad = self.splash.validate_region(pad, 'pad')
        result = self.element.png(width, scale_method=scale_method, pad=pad)

        if not result:
            return None
        return BinaryCapsule(result, 'image/png')

    @command()
    def jpeg(self, width=None, scale_method=None, quality=None, pad=None):
        if width is not None:
            width = int(width)
        if quality is not None:
            quality = int(quality)

        if pad is not None and isinstance(pad, (int, float)):
            pad = (pad, pad, pad, pad)
        pad = self.splash.validate_region(pad, 'pad')
        result = self.element.jpeg(width, scale_method=scale_method,
                                   quality=quality, pad=pad)

        if not result:
            return None
        return BinaryCapsule(result, 'image/jpeg')

    @command()
    def visible(self):
        return self.element.visible()

    @command()
    def focused(self):
        return self.element.focused()

    @command()
    def text(self):
        return self.element.text()

    @command()
    def info(self):
        return self.element.info()

    @command(error_as_flag=True, result_as_flag=True)
    def field_value(self):
        return self.element.field_value()

    @command(error_as_flag=True)
    def form_values(self, values='auto'):
        if values not in ['auto', 'first', 'list']:
            raise ScriptError({
                "argument": "multi",
                "message": "element:form_values values can only be "
                           "'auto', 'first' or 'list'",
                "splash_method": "form_values",
            })

        return self.element.form_values(values)

    @command(error_as_flag=True, table_argument=True, decode_arguments=False)
    def fill(self, values):
        if lupa.lua_type(values) != 'table':
            raise ScriptError({
                "argument": "values",
                "message": "element:fill values is not a table",
                "splash_method": "fill",
            })

        # marking all tables as arrays by default
        for key, value in values.items():
            if lupa.lua_type(value) == 'table':
                _mark_table_as_array(self.lua, value)

        values = self.lua.lua2python(values)

        return self.element.fill(values)

    @command(error_as_flag=True)
    def send_keys(self, text):
        return self.element.send_keys(text)

    @command(error_as_flag=True)
    def send_text(self, text):
        return self.element.send_text(text)

    @command(error_as_flag=True)
    def submit(self):
        return self.element.submit()


_ExposedElement.init_properties()
_ExposedElement.init_methods()


class _ExposedElementStyle(BaseExposedObject):
    def __init__(self, lua, exceptions, element):
        self.element = element
        super(_ExposedElementStyle, self).__init__(lua, exceptions)

    @command()
    def _get_style(self, name):
        return self.element.get_node_style(name)

    @command()
    def _set_style(self, name, value):
        return self.element.set_node_style(name, value)


class _ExposedEvent(BaseExposedObject):
    def __init__(self, lua, exceptions, event):
        self.event = event
        super(_ExposedEvent, self).__init__(lua, exceptions)

    @command()
    def _get_property(self, name):
        return self.event[name]

    @command()
    def preventDefault(self):
        return self.event.preventDefault()

    @command()
    def stopImmediatePropagation(self):
        return self.event.stopImmediatePropagation()

    @command()
    def stopPropagation(self):
        return self.event.stopPropagation()


requires_request = requires_attr(
    "request",
    lambda self, meth, attr_name: self._on_request_required(meth, attr_name)
)
requires_response = requires_attr(
    "response",
    lambda self, meth, attr_name: self._on_response_required(meth, attr_name)
)


class _ExposedRequest(BaseExposedObject):
    """ Read-only QNetworkRequest wrapper for Lua """
    _attribute_whitelist = ['url', 'method', 'headers', 'info']

    def __init__(self, lua, exceptions, url, method, headers, info):
        super(_ExposedRequest, self).__init__(lua, exceptions)
        self.url = url
        self.method = method
        # TODO: make info and headers attributes lazy
        self.headers = self.lua.python2lua(headers, encoding='latin1')
        self.info = self.lua.python2lua(info)

    @classmethod
    def from_reply(cls, lua, exceptions, reply):
        har_request = request2har(reply.request(), reply.operation())
        return cls.from_har(lua, exceptions, har_request)

    @classmethod
    def from_har(cls, lua, exceptions, har_request):
        headers = {h['name']: h['value'] for h in har_request['headers']}
        return cls(lua, exceptions,
            url=har_request['url'],
            method=har_request['method'],
            headers=headers,
            info=har_request,
        )


class _ExposedBoundRequest(BaseExposedObject):
    """ QNetworkRequest wrapper for Lua """
    _attribute_whitelist = ['url', 'method', 'headers', 'info']

    def __init__(self, lua, exceptions, request, operation, outgoing_data):
        super(_ExposedBoundRequest, self).__init__(lua, exceptions)
        self.request = request

        har_request = request2har(request, operation, outgoing_data)
        self.url = self.lua.python2lua(har_request['url'])
        self.method = self.lua.python2lua(har_request['method'])
        # TODO: make info and headers attributes lazy
        self.info = self.lua.python2lua(har_request)
        self.headers = self.lua.python2lua(get_headers_dict(request))

    def clear(self):
        super(_ExposedBoundRequest, self).clear()
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
    def enable_response_body(self):
        self.request.track_response_body = True

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
        self.request.setRawHeader(to_bytes(name), to_bytes(value))

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
    """
    Response object exposed to Lua. This Response type doesn't provide methods
    to manupulate a response.
    """
    _attribute_whitelist = ["headers", "request"]

    def __init__(self, lua, exceptions, reply, exposed_request,
                 har_entry=None, content=None):
        super(_ExposedResponse, self).__init__(lua, exceptions)
        self.headers = self.lua.python2lua(get_headers_dict(reply))

        if har_entry is None:
            resp_info = reply2har(reply, content=content)
        else:
            resp_info = har_entry['response']

        self.request = exposed_request
        self._content = content
        self._info = resp_info
        self._info_lua = None

    @lua_property("body")
    @command()
    def get_body(self):
        if not hasattr(self, '_body_binary'):
            self._body_binary = self._get_body_object()
            self._content = None
        return self._body_binary

    def _get_body_object(self):
        body = self._content or get_response_body_bytes(self._info)
        if body is None:
            return None
        content_type = self._info['content']['mimeType']
        return BinaryCapsule(body, content_type)

    @lua_property("info")
    @command()
    def get_info(self):
        if self._info_lua is None:
            self._info_lua = self.lua.python2lua(self._info)
        return self._info_lua

    @lua_property("status")
    @command()
    def get_status(self):
        return self._info['status']

    @lua_property("url")
    @command()
    def get_url(self):
        return self._info['url']

    @lua_property("ok")
    @command()
    def is_ok(self):
        return self._info['ok']

    def clear(self):
        super(_ExposedResponse, self).clear()
        self.request = None
        self._info = None
        self._info_lua = None
        self._body_binary = None
        self._content = None
        self.headers = None

    def _on_response_required(self, meth, attr_name):
        raise ScriptError({
            "message": "response is used outside a callback",
            "type": ScriptError.SPLASH_LUA_ERROR,
            "splash_method": None,
            "response_method": meth.__name__,
        })


class _ExposedBoundResponse(_ExposedResponse):
    """
    Response object exposed to Lua. This Response type provides
    a way to manipulate the response (currently it is possible to
    abort downloading).
    """
    def __init__(self, lua, exceptions, reply, exposed_request,
                 har_entry=None, content=None):
        super(_ExposedBoundResponse, self).__init__(
            lua, exceptions, reply, exposed_request, har_entry, content,
        )
        self.response = reply

    def clear(self):
        super(_ExposedBoundResponse, self).clear()
        self.response = None

    @command()
    @requires_response
    def abort(self):
        self.response.abort()


class Extras(BaseExposedObject):
    """
    Extra features exposed to Lua via custom modules.

    TODO: users should be able to expose their own plugins
    """
    def __init__(self, lua, exceptions):
        super(Extras, self).__init__(lua, exceptions)
        wrapper = self.lua.eval("require('extras')")
        self._wrapped = wrapper._create(self)

    @command(decode_arguments=False)
    def base64_encode(self, data):
        if isinstance(data, BinaryCapsule):
            return data.as_b64()
        data = to_bytes(data)
        return base64.b64encode(data)

    @command()
    def base64_decode(self, data):
        return base64.b64decode(data)

    @command(table_argument=True)
    def json_encode(self, obj):
        pyobj = self.lua.lua2python(obj)
        return json.dumps(pyobj, cls=SplashJSONEncoder)

    @command()
    def json_decode(self, s):
        return json.loads(s)

    @command(decode_arguments=False)
    def treat_as_binary(self, s, content_type=None):
        s = self.lua.lua2python(s, max_depth=1, encoding=None)
        content_type = self.lua.lua2python(content_type, max_depth=1,
                                           encoding=None)

        if isinstance(s, BinaryCapsule):
            if content_type is not None:
                return BinaryCapsule(s.data, content_type)
            else:
                return s

        if content_type is None:
            content_type = b'application/octet-stream'
        return BinaryCapsule(s, content_type)

    @command()
    def treat_as_string(self, s):
        assert isinstance(s, BinaryCapsule)
        return s.data, s.content_type

    def inject_to_globals(self):
        self.lua.add_to_globals("__extras", self._wrapped)
        self.lua.add_allowed_module("base64")
        self.lua.add_allowed_module("json")
        self.lua.add_allowed_module("treat")


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
    def __init__(self, lua, splash, log, sandboxed):
        self.exceptions = splash.exceptions
        super(MainCoroutineRunner, self).__init__(
            lua=lua,
            splash=splash,
            log=log,
            sandboxed=sandboxed
        )

    def start(self, main_coro, return_result=None, return_error=None):
        self.exceptions.clear()
        args = [self.splash.get_wrapped()]
        super(MainCoroutineRunner, self).start(main_coro, args, return_result, return_error)

    def on_result(self, result):
        # Request writer expects JSON-like values and misbehaves when the
        # result is a tuple.  Wrap tuples to be returned as JSON lists, as they
        # would be serialized like that anyway.
        #
        # FIXME: maybe request writer must be fixed?
        if isinstance(result, tuple):
            result = list(result)
        self.return_result((
            result,
            self.splash.result_content_type(),
            self.splash.result_headers(),
            self.splash.result_status_code(),
        ))

    def on_lua_error(self, lua_exception):
        py_exception = self.exceptions.get_last()

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
            'message': str(ex.args[0]),
        })


class LuaRender(RenderScript):
    default_min_log_level = 2

    @stop_on_error
    def start(self, lua_source, sandboxed, lua_package_path,
              lua_sandbox_allowed_modules):
        self.exceptions = StoredExceptions()
        self.log(lua_source)
        self.sandboxed = sandboxed
        self.lua = SplashLuaRuntime(
            sandboxed=sandboxed,
            lua_package_path=lua_package_path,
            lua_sandbox_allowed_modules=lua_sandbox_allowed_modules
        )
        self.splash = Splash(self.lua, self.exceptions, self.tab,
                             self.render_options, log=self.log)
        self.extras = Extras(self.lua, self.exceptions)
        self.extras.inject_to_globals()

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
                'message': to_unicode(e.args[0]),
            })
        except lupa.LuaError as e:
            # Error happened before starting coroutine
            info = parse_error_message(e.args[0])
            info.update({
                "type": ScriptError.LUA_INIT_ERROR,
                "message": to_unicode(e.args[0]),
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

    def close(self):
        self.splash.clear()
        super(LuaRender, self).close()

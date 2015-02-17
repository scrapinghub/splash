# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import functools
import itertools
import resource
import time
import sys
from twisted.internet import defer

import lupa

from splash.browser_tab import JsError
from splash.lua_runner import (
    BaseScriptRunner,
    ScriptError,
    ImmediateResult,
    AsyncCommand
)
from splash.qtrender import RenderScript, stop_on_error
from splash.lua import get_main, get_main_sandboxed
from splash.har.qt import reply2har
from splash.render_options import BadOption, RenderOptions
from splash.utils import truncated, BinaryCapsule
from splash.qtutils import REQUEST_ERRORS_SHORT
from splash.lua_runtime import SplashLuaRuntime


class AsyncBrowserCommand(AsyncCommand):
    def __repr__(self):
        kwargs = self.kwargs.copy()
        if 'callback' in kwargs:
            kwargs['callback'] = '<a callback>'
        if 'errback' in kwargs:
            kwargs['errback'] = '<an errback>'
        kwargs_repr = truncated(repr(kwargs), 400, "...[long kwargs truncated]")
        return "%s(id=%r, name=%r, kwargs=%s)" % (self.__class__.__name__, self.id, self.name, kwargs_repr)


def command(async=False, can_raise_async=False, table_argument=False):
    """ Decorator for marking methods as commands available to Lua """
    def decorator(meth):
        if not table_argument:
            meth = lupa.unpacks_lua_table_method(meth)
        meth = exceptions_as_return_values(
            can_raise(
                emits_lua_objects(meth)
            )
        )
        meth._is_command = True
        meth._is_async = async
        meth._can_raise_async = can_raise_async
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


def is_command(meth):
    """ Return True if method is an exposed Lua command """
    return getattr(meth, '_is_command', False)


def can_raise(meth):
    """
    Decorator for preserving Python exceptions raised in Python
    methods called from Lua.
    """
    @functools.wraps(meth)
    def wrapper(self, *args, **kwargs):
        try:
            return meth(self, *args, **kwargs)
        except ScriptError as e:
            self._exceptions.append(e)
            raise
        except BaseException as e:
            self._exceptions.append(ScriptError(e))
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
                    error_repr: e.toString(),
                }
            }
        })(%(func_text)s)
        """ % {"func_text": func_text, "args": args_text}

        # print(wrapper_script)
        res = self.tab.evaljs(wrapper_script)

        if not isinstance(res, dict):
            raise ScriptError("[lua] unknown error during JS function call: %r; %r" % (res, wrapper_script))

        if res["error"]:
            raise ScriptError("[lua] error during JS function call: %r" % (res.get("error_repr", "<unknown error>"),))

        return res.get("result")


class Splash(object):
    """
    This object is passed to Lua script as an argument to 'main' function
    (wrapped in 'Splash' Lua object; see :file:`splash/lua_modules/splash.lua`).
    """
    _result_content_type = None
    _attribute_whitelist = ['commands', 'args']

    def __init__(self, lua, tab, render_options=None):
        """
        :param SplashLuaRuntime lua: Lua wrapper
        :param splash.browser_tab.BrowserTab tab: BrowserTab object
        :param splash.render_options.RenderOptions render_options: arguments
        """
        self.tab = tab
        self.lua = lua

        self._exceptions = []
        self._command_ids = itertools.count()

        if isinstance(render_options, RenderOptions):
            self.args = self.lua.python2lua(render_options.data)
        elif isinstance(render_options, dict):
            self.args = self.lua.python2lua(render_options)
        elif render_options is None:
            self.args = self.lua.python2lua({})
        else:
            raise ValueError("Invalid render_options type: %s" % render_options.__class__)

        self.attr_whitelist = []
        commands = {}
        for name in dir(self):
            value = getattr(self, name)
            if is_command(value):
                self.attr_whitelist.append(name)
                commands[name] = self.lua.table_from({
                    'is_async': getattr(value, '_is_async'),
                    'returns_error_flag': getattr(value, '_returns_error_flag', False),
                    'can_raise_async': getattr(value, '_can_raise_async', False),
                })
        self.commands = self.lua.python2lua(commands)
        self.attr_whitelist.extend(self._attribute_whitelist)
        self.lua.add_allowed_object(self, self.attr_whitelist)

        wrapper = self.lua.eval("require('splash')")
        self._wrapped = wrapper.private_create(self)

    def init_dispatcher(self, return_func):
        """
        :param callable return_func: function that continues the script
        """
        self._return = return_func

    @command(async=True)
    def wait(self, time, cancel_on_redirect=False, cancel_on_error=True):
        time = float(time)
        if time < 0:
            raise BadOption("splash:wait time can't be negative")

        cmd_id = next(self._command_ids)

        def success():
            self._return(cmd_id, True)

        def redirect():
            self._return(cmd_id, None, 'redirect')

        def error():
            self._return(cmd_id, None, 'error')

        return AsyncBrowserCommand(cmd_id, "wait", dict(
            time_ms = time*1000,
            callback = success,
            onredirect = redirect if cancel_on_redirect else False,
            onerror = error if cancel_on_error else False,
        ))

    @command(async=True)
    def go(self, url, baseurl=None, headers=None):
        if url is None:
            raise ScriptError("'url' is required for splash:go")

        if self.tab.web_page.navigation_locked:
            return ImmediateResult((None, "navigation_locked"))

        cmd_id = next(self._command_ids)

        def success():
            code = self.tab.last_http_status()
            if code and 400 <= code < 600:
                # return HTTP errors as errors
                self._return(cmd_id, None, "http%d" % code)
            else:
                self._return(cmd_id, True)

        def error():
            self._return(cmd_id, None, "error")

        return AsyncBrowserCommand(cmd_id, "go", dict(
            url=url,
            baseurl=baseurl,
            callback=success,
            errback=error,
            headers=self.lua.lua2python(headers, max_depth=3),
        ))

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
        return BinaryCapsule(result)

    @command()
    def har(self):
        return self.tab.har()

    @command()
    def history(self):
        return self.tab.history()

    @command()
    def stop(self):
        self.tab.stop_loading()

    @command()
    def evaljs(self, snippet):
        return self.tab.evaljs(snippet)

    @command()
    def runjs(self, snippet):
        try:
            self.tab.runjs(snippet)
            return True
        except JsError as e:
            return None, e.args[0]

    @command(async=True, can_raise_async=True)
    def wait_for_resume(self, snippet, timeout=0):
        cmd_id = next(self._command_ids)

        def callback(result):
            self._return(cmd_id, self.lua.python2lua(result))

        def errback(msg, raise_):
            self._return(cmd_id, None, "JavaScript error: %s" % msg, raise_)

        return AsyncBrowserCommand(cmd_id, "wait_for_resume", dict(
            js_source=snippet,
            callback=callback,
            errback=errback,
            timeout=timeout,
        ))

    @command()
    def private_jsfunc(self, func):
        return _WrappedJavascriptFunction(self, func)

    @command(async=True)
    def http_get(self, url, headers=None, follow_redirects=True):
        if url is None:
            raise ScriptError("'url' is required for splash:http_get")

        cmd_id = next(self._command_ids)

        def callback(reply):
            reply_har = reply2har(reply, include_content=True, binary_content=True)
            self._return(cmd_id, self.lua.python2lua(reply_har))

        return AsyncBrowserCommand(cmd_id, "http_get", dict(
            url=url,
            callback=callback,
            headers=self.lua.lua2python(headers, max_depth=3),
            follow_redirects=follow_redirects,
        ))

    @command(async=True)
    def autoload(self, source_or_url=None, source=None, url=None):
        if len([a for a in [source_or_url, source, url] if a is not None]) != 1:
            raise ScriptError("splash:autoload requires a single argument")

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
            cmd_id = next(self._command_ids)
            def callback(reply):
                if reply.error():
                    reason = REQUEST_ERRORS_SHORT.get(reply.error(), '?')
                    self._return(cmd_id, None, reason)
                else:
                    source = bytes(reply.readAll())
                    self.tab.autoload(source)
                    self._return(cmd_id, True)

            return AsyncBrowserCommand(cmd_id, "http_get", dict(
                url=url,
                callback=callback
            ))

    @command(async=True)
    def set_content(self, data, mime_type=None, baseurl=None):
        cmd_id = next(self._command_ids)

        def success():
            self._return(cmd_id, True)

        def error():
            self._return(cmd_id, None, "error")

        return AsyncBrowserCommand(cmd_id, "set_content", dict(
            data=data,
            baseurl=baseurl,
            mime_type=mime_type,
            callback=success,
            errback=error,
        ))

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
            raise ScriptError("splash:set_result_content_type() argument must be a string")
        self._result_content_type = content_type

    @command()
    def set_user_agent(self, value):
        if not isinstance(value, basestring):
            raise ScriptError("splash:set_user_agent() argument must be a string")
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

    @command()
    def set_images_enabled(self, enabled):
        if enabled is not None:
            self.tab.set_images_enabled(int(enabled))

    @command()
    def status_code(self):
        return self.tab.last_http_status()

    @command()
    def url(self):
        return self.tab.url

    @command()
    def get_perf_stats(self):
        """Return performance-related statistics."""
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        # on Mac OS X ru_maxrss is in bytes, on Linux it is in KB
        rss_mul = 1 if sys.platform == 'darwin' else 1024
        return {'maxrss': rusage.ru_maxrss * rss_mul,
                'cputime': rusage.ru_utime + rusage.ru_stime,
                'walltime': time.time()}

    def get_real_exception(self):
        if self._exceptions:
            return self._exceptions[-1]

    def clear_exceptions(self):
        self._exceptions[:] = []

    def result_content_type(self):
        if self._result_content_type is None:
            return None
        return str(self._result_content_type)

    def get_wrapped(self):
        """ Return a Lua wrapper for this object. """
        return self._wrapped

    def run_async_command(self, cmd):
        """ Execute _AsyncCommand """
        meth = getattr(self.tab, cmd.name)
        return meth(**cmd.kwargs)


class SplashScriptRunner(BaseScriptRunner):
    """
    An utility class for running Lua coroutines that interact with Splash.
    """
    def __init__(self, lua, splash, log, sandboxed):
        self.splash = splash
        self.splash.init_dispatcher(self.dispatch)
        super(SplashScriptRunner, self).__init__(lua=lua, log=log, sandboxed=sandboxed)

    def start(self, main_coro, return_result, return_error):
        self.return_result = return_result
        self.return_error = return_error
        self.splash.clear_exceptions()
        super(SplashScriptRunner, self).start(main_coro, [self.splash.get_wrapped()])

    def on_result(self, result):
        self.return_result((result, self.splash.result_content_type()))

    def on_async_command(self, cmd):
        self.splash.run_async_command(cmd)

    def on_lua_error(self, lua_exception):
        ex = self.splash.get_real_exception()
        if not ex:
            return
        self.log("[lua] LuaError is caused by %r" % ex)
        if isinstance(ex, ScriptError):
            ex.enrich_from_lua_error(lua_exception)
        raise ex

    @stop_on_error
    def dispatch(self, cmd_id, *args):
        super(SplashScriptRunner, self).dispatch(cmd_id, *args)


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

        self.runner = SplashScriptRunner(
            lua=self.lua,
            splash=self.splash,
            log=self.log,
            sandboxed=sandboxed,
        )

        try:
            main_coro = self.get_main(lua_source)
        except (ValueError, lupa.LuaSyntaxError, lupa.LuaError) as e:
            raise ScriptError("lua_source: " + repr(e))

        self.runner.start(
            main_coro=main_coro,
            return_result=self.return_result,
            return_error=self.return_error,
        )

    def get_main(self, lua_source):
        if self.sandboxed:
            main, env = get_main_sandboxed(self.lua, lua_source)
        else:
            main, env = get_main(self.lua, lua_source)
        return self.lua.create_coroutine(main)


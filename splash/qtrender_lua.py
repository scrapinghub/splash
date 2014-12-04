# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import functools
import itertools

import lupa

from splash.qtrender import RenderScript, stop_on_error
from splash.lua import (
    get_new_runtime,
    get_main,
    get_main_sandboxed,
    get_script_source,
    lua2python,
    python2lua,
)
from splash.render_options import BadOption
from splash.utils import truncated, BinaryCapsule


class ScriptError(BadOption):

    def enrich_from_lua_error(self, e):
        if not isinstance(e, lupa.LuaError):
            return

        self_repr = repr(self.args[0])
        if self_repr in e.args[0]:
            self.args = (e.args[0],) + self.args[1:]
        else:
            self.args = (e.args[0] + "; " + self_repr,) + self.args[1:]


class _AsyncBrowserCommand(object):

    def __init__(self, id, name, kwargs):
        self.id = id
        self.name = name
        self.kwargs = kwargs

    def __repr__(self):
        kwargs = self.kwargs.copy()
        if 'callback' in kwargs:
            kwargs['callback'] = '<a callback>'
        if 'errback' in kwargs:
            kwargs['errback'] = '<an errback>'
        kwargs_repr = truncated(repr(kwargs), 400, "...[long kwargs truncated]")
        return "%s(id=%r, name=%r, kwargs=%s)" % (self.__class__.__name__, self.id, self.name, kwargs_repr)


def command(async=False):
    """ Decorator for marking methods as commands available to Lua """
    def decorator(meth):
        meth = exceptions_as_return_values(
            can_raise(
                emits_lua_objects(
                    lupa.unpacks_lua_table_method(meth)
                )
            )
        )
        meth._is_command = True
        meth._is_async = async
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
        return python2lua(self.lua, res)
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
    splash/scripts/splash.lua wrap_errors decorator.
    """
    @functools.wraps(meth)
    def wrapper(self, *args, **kwargs):
        try:
            result = meth(self, *args, **kwargs)
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
        args = lua2python(self.lua, args)
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
        res = self.tab.runjs(wrapper_script)

        if not isinstance(res, dict):
            raise ScriptError("[lua] unknown error during JS function call: %r; %r" % (res, wrapper_script))

        if res["error"]:
            raise ScriptError("[lua] error during JS function call: %r" % (res.get("error_repr", "<unknown error>"),))

        return res.get("result")


class Splash(object):
    """
    This object is passed to Lua script as an argument to 'main' function
    (wrapped in 'Splash' Lua object; see :file:`scripts/splash.lua`).
    """
    _result_content_type = None
    _attribute_whitelist = ['commands', 'args']

    def __init__(self, tab, return_func, render_options, sandboxed):
        """
        :param splash.browser_tab.BrowserTab tab: BrowserTab object
        :param callable return_func: function that continues the script
        :param splash.render_options.RenderOptions render_options: arguments
        :param bool sandboxed: whether the script should be sandboxed
        """
        self.lua = self._create_runtime()
        self.tab = tab
        self.sandboxed = sandboxed
        self._return = return_func
        self._exceptions = []
        self._command_ids = itertools.count()

        self.args = python2lua(self.lua, render_options.data)

        commands = {}
        for name in dir(self):
            value = getattr(self, name)
            if is_command(value):
                commands[name] = self.lua.table_from({
                    'is_async': getattr(value, '_is_async'),
                    'returns_error_flag': getattr(value, '_returns_error_flag', False),
                })
        self.commands = python2lua(self.lua, commands)

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

        return _AsyncBrowserCommand(cmd_id, "wait", dict(
            time_ms = time*1000,
            callback = success,
            onredirect = redirect if cancel_on_redirect else False,
            onerror = error if cancel_on_error else False,
        ))

    @command(async=True)
    def go(self, url, baseurl=None):
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

        return _AsyncBrowserCommand(cmd_id, "go", dict(
            url=url,
            baseurl=baseurl,
            callback=success,
            errback=error
        ))

    @command()
    def html(self):
        return self.tab.html()

    @command()
    def png(self, width=None, height=None):
        if width is not None:
            width = int(width)
        if height is not None:
            height = int(height)
        result = self.tab.png(width, height, b64=False)
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
    def runjs(self, snippet):
        res = self.tab.runjs(snippet)
        return res

    @command()
    def jsfunc_private(self, func):
        return _WrappedJavascriptFunction(self, func)

    @command()
    def set_result_content_type(self, content_type):
        if not isinstance(content_type, basestring):
            raise ScriptError("splash:set_result_content_type() argument must be a string")
        self._result_content_type = content_type

    @command()
    def set_viewport(self, size):
        if size is None:
            return
        return self.tab.set_viewport(size)

    @command()
    def set_images_enabled(self, enabled):
        if enabled is not None:
            self.tab.set_images_enabled(int(enabled))

    @command()
    def status_code(self):
        return self.tab.last_http_status()

    def get_real_exception(self):
        if self._exceptions:
            return self._exceptions[-1]

    def result_content_type(self):
        if self._result_content_type is None:
            return None
        return str(self._result_content_type)

    def get_wrapper(self):
        """
        Return a Lua wrapper for this object.
        """
        # FIXME: cache file contents
        splash_lua_code = get_script_source("splash.lua")
        self.lua.execute(splash_lua_code)
        wrapper = self.lua.globals()["Splash"]
        return wrapper(self)

    def start_main(self, lua_source):
        """
        Start "main" function and return it as a coroutine.
        """
        splash_obj = self.get_wrapper()
        if self.sandboxed:
            main, env = get_main_sandboxed(self.lua, lua_source)
            # self.script_globals = env  # XXX: does it work well with GC?
            create_coroutine = self.lua.globals()["create_sandboxed_coroutine"]
            coro = create_coroutine(main)
            return coro(splash_obj)
        else:
            main, env = get_main(self.lua, lua_source)
            # self.script_globals = env  # XXX: does it work well with GC?
            return main.coroutine(splash_obj)

    def instruction_count(self):
        if not self.sandboxed:
            return -1
        try:
            return self.lua.eval("instruction_count")
        except Exception as e:
            print(e)
            return -1

    def run_async_command(self, cmd):
        """ Execute _AsyncCommand """
        meth = getattr(self.tab, cmd.name)
        return meth(**cmd.kwargs)

    def lua2python(self, obj):
        return lua2python(self.lua, obj, binary=True, strict=True)

    def _create_runtime(self):
        """
        Return a restricted Lua runtime.
        Currently it only allows accessing attributes of this object.
        """
        return get_new_runtime(
            attribute_handlers=(self._attr_getter, self._attr_setter)
        )

    def _attr_getter(self, obj, attr_name):

        if not isinstance(attr_name, basestring):
            raise AttributeError("Non-string lookups are not allowed (requested: %r)" % attr_name)

        if isinstance(attr_name, basestring) and attr_name.startswith("_"):
            raise AttributeError("Access to private attribute %r is not allowed" % attr_name)

        if obj is not self:
            raise AttributeError("Access to object %r is not allowed" % obj)

        value = getattr(obj, attr_name)
        if not is_command(value) and not attr_name in self._attribute_whitelist:
            raise AttributeError("Access to private attribute %r is not allowed" % attr_name)

        return value

    def _attr_setter(self, obj, attr_name, value):
        raise AttributeError("Direct writing to Python objects is not allowed")


class LuaRender(RenderScript):

    default_min_log_level = 2
    result = ''
    _START_CMD = '__START__'
    _waiting_for_result_id = _START_CMD

    @stop_on_error
    def start(self, lua_source, sandboxed):
        self.log(lua_source)
        self.sandboxed = sandboxed
        self.splash = Splash(
            tab=self.tab,
            return_func=self.dispatch,
            render_options=self.render_options,
            sandboxed=sandboxed
        )
        try:
            self.coro = self.splash.start_main(lua_source)
        except (ValueError, lupa.LuaSyntaxError, lupa.LuaError) as e:
            raise ScriptError("lua_source: " + repr(e))

        self.dispatch(self._START_CMD)

    @stop_on_error
    def dispatch(self, cmd_id, *args):
        """ Execute the script """
        self.log("[lua] dispatch cmd_id={}, args={!s}".format(cmd_id, args))

        self.log(
            "[lua] arguments are for command %s, waiting for result of %s" % (cmd_id, self._waiting_for_result_id),
            min_level=3,
        )
        if cmd_id != self._waiting_for_result_id:
            self.log("[lua] skipping an out-of-order result {!r}".format(args), min_level=1)
            return

        while True:
            try:
                args = args or None

                # Got arguments from an async command; send them to coroutine
                # and wait for the next async command.
                self.log("[lua] send %s" % (args,))
                cmd = self.coro.send(args)  # cmd is a next async command

                args = None  # don't re-send the same value
                cmd_repr = truncated(repr(cmd), max_length=400, msg='...[long result truncated]')
                self.log("[lua] got {}".format(cmd_repr))
                self._print_instructions_used()

            except StopIteration:
                # "main" coroutine is stopped;
                # previous result is a final result returned from "main"
                self.log("[lua] returning result")
                try:
                    res = self.splash.lua2python(self.result)
                except ValueError as e:
                    # can't convert result to a Python object -> requets was bad
                    raise ScriptError("'main' returned bad result. {!s}".format(e))

                self._print_instructions_used()
                self.return_result((res, self.splash.result_content_type()))
                return
            except lupa.LuaError as e:
                # Lua script raised an error
                self._print_instructions_used()
                self.log("[lua] caught LuaError %r" % e)
                ex = self.splash.get_real_exception()
                if ex:
                    self.log("[lua] LuaError is caused by %r" % ex)
                    if isinstance(ex, ScriptError):
                        ex.enrich_from_lua_error(e)
                    raise ex
                # XXX: are Lua errors bad requests?
                raise ScriptError("unhandled Lua error: {!s}".format(e))

            if isinstance(cmd, _AsyncBrowserCommand):
                self.log("[lua] executing {!r}".format(cmd))
                self._waiting_for_result_id = cmd.id
                self.splash.run_async_command(cmd)
                return
            else:
                self.log("[lua] got non-command")

                if isinstance(cmd, tuple):
                    raise ScriptError("'main' function must return a single result")

                self.result = cmd

    def _print_instructions_used(self):
        if self.sandboxed:
            self.log("[lua] instructions used: %d" % self.splash.instruction_count())


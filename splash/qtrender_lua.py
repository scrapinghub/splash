# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import functools
import inspect
from collections import namedtuple
import lupa
from splash.qtrender import RenderScript, stop_on_error
from splash.lua import (
    table_as_kwargs_method,
    get_new_runtime,
    start_main,
    get_script_source,
    lua2python,
    python2lua,
)
from splash.render_options import BadOption


class ScriptError(BadOption):
    pass


class _AsyncCommand(object):
    def __init__(self, name, kwargs):
        self.name = name
        self.kwargs = kwargs

    def __repr__(self):
        return "_AsyncCommand(name=%r, kwargs=%r)" % (self.name, self.kwargs)


def command(async=False):
    """ Decorator for marking methods as commands available to Lua """
    def decorator(meth):
        meth = can_raise(emits_lua_objects(table_as_kwargs_method(meth)))
        meth._is_command = True
        meth._is_async = async
        return meth
    return decorator


def emits_lua_objects(meth):
    """
    This decorator makes method convert results to
    native Lua formats when possible
    """
    def wrapper(self, *args, **kwargs):
        res = meth(self, *args, **kwargs)
        return python2lua(self.lua, res)
    return functools.wraps(meth)(wrapper)


def is_command(meth):
    """ Return True if method is an exposed Lua command """
    return getattr(meth, '_is_command', False)


def can_raise(func):
    """
    Decorator for preserving Python exceptions raised in Python
    functions called from Lua.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except ScriptError as e:
            self._exceptions.append(e)
            raise
        except Exception as e:
            self._exceptions.append(ScriptError(e))
            raise
    return wrapper


class Splash(object):
    """
    This object is passed to Lua script as an argument to 'main' function
    (wrapped in 'Splash' Lua object; see :file:`scripts/splash.lua`).
    """
    _result_content_type = None
    _attribute_whitelist = ['commands']

    def __init__(self, tab, return_func, render_options):
        """
        :param splash.browser_tab.BrowserTab tab: BrowserTab object
        :param callable return_func: function that continues the script
        """
        self.lua = self._create_runtime()
        self.tab = tab
        self.render_options = render_options
        self._return = return_func
        self._exceptions = []

        commands = {}
        for name in dir(self):
            value = getattr(self, name)
            if is_command(value):
                commands[name] = getattr(value, '_is_async')
        self.commands = python2lua(self.lua, commands)

    @command(async=True)
    def wait(self, time, cancel_on_redirect=False):
        # TODO: make sure it returns 'not_cancelled' flag
        return _AsyncCommand("wait", dict(
            time_ms=time*1000,
            callback=self._wait_success,
            onredirect=cancel_on_redirect,
        ))

    def _wait_success(self):
        self._return(True)

    @command(async=True)
    def go(self, url, baseurl=None):
        return _AsyncCommand("go", dict(
            url=url,
            baseurl=baseurl,
            callback=self._go_success,
            errback=self._go_error)
        )

    def _go_success(self):
        self._return(True)

    def _go_error(self):
        # TODO: better error description
        self._return(None, "error loading page")

    @command()
    def html(self):
        return self.tab.html()

    @command()
    def png(self, width=None, height=None, base64=True):
        # TODO: with base64=False return "BinaryCapsule"
        # to prevent lupa from trying to encode/decode it.
        return self.tab.png(width, height, b64=base64)

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
    def runjs(self, js):
        res = self.tab.runjs(js)
        return res

    @command()
    def set_result_content_type(self, content_type):
        if not isinstance(content_type, basestring):
            raise ScriptError("splash:set_result_content_type() argument must be a string")
        self._result_content_type = content_type

    @command()
    def set_viewport(self, size):
        return self.tab.set_viewport(size)

    def raise_stored(self):
        if self._exceptions:
            raise self._exceptions[-1]

    def result_content_type(self):
        if self._result_content_type is None:
            return None
        return str(self._result_content_type)

    def get_wrapper(self):
        """
        Return a Lua wrapper for this object.
        """
        # FIXME: cache file contents
        code = get_script_source("splash.lua")
        self.lua.execute(code)
        wrapper = self.lua.globals()["Splash"]
        return wrapper(self)

    def start_main(self, lua_source):
        """
        Start "main" function and return it as a coroutine.
        """
        return start_main(self.lua, lua_source, args=[self.get_wrapper()])

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

    @stop_on_error
    def start(self, lua_source):
        self.log(lua_source)
        self.splash = Splash(self.tab, self.dispatch, self.render_options)
        try:
            self.coro = self.splash.start_main(lua_source)
        except (ValueError, lupa.LuaSyntaxError, lupa.LuaError) as e:
            raise ScriptError("lua_source: " + repr(e))

        self.dispatch()

    @stop_on_error
    def dispatch(self, *args):
        """ Execute the script """
        self.log("[lua] dispatch {!s}".format(args))

        while True:
            try:
                self.log("[lua] send %s" % (args,))
                cmd = self.coro.send(args or None)
                self.log("[lua] got {!r}".format(cmd))
            except StopIteration:
                # previous result is a final result returned from "main"
                self.log("[lua] returning result")
                try:
                    res = lua2python(self.result, binary=True, strict=True)
                except ValueError as e:
                    # can't convert result to a Python object -> requets was bad
                    raise ScriptError("'main' returned bad result. {!s}".format(e))

                self.return_result((res, self.splash.result_content_type()))
                return
            except lupa.LuaError as e:
                self.log("[lua] LuaError %r" % e)
                self.splash.raise_stored()
                # XXX: are Lua errors bad requests?
                raise ScriptError("unhandled Lua error: {!s}".format(e))

            if isinstance(cmd, _AsyncCommand):
                self.log("[lua] executing {!r}".format(cmd))
                meth = getattr(self.tab, cmd.name)
                meth(**cmd.kwargs)
                return
            else:
                self.log("[lua] got non-command")

                if isinstance(cmd, tuple):
                    raise ScriptError("'main' function must return a single result")

                self.result = cmd

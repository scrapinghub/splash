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
    def decorator(func):
        func = table_as_kwargs_method(func)
        func._is_command = True
        func._is_async = async
        return can_raise(func)
    return decorator


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
    This object is passed to Lua script as an argument to 'main' function.
    """
    _result_content_type = None
    _attribute_whitelist = ['commands']

    def __init__(self, tab, return_func, render_options):
        """
        :param splash.browser_tab.BrowserTab tab: BrowserTab object
        :param callable dispatch_func: function that continues the script
        """
        self._lua = self._create_runtime()
        self._tab = tab
        self._return = return_func
        self._render_options = render_options
        self._exceptions = []

        commands = {}
        for name in dir(self):
            value = getattr(self, name)
            if is_command(value):
                commands[name] = getattr(value, '_is_async')
        self.commands = self._lua.table(**commands)

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
        return self._tab.html()

    @command()
    def png(self, width=None, height=None, base64=True):
        return self._tab.png(width, height, b64=base64)

    @command()
    def har(self):
        return self._tab.har()

    @command()
    def history(self):
        return self._tab.history()

    @command()
    def stop(self):
        self._tab.stop_loading()

    @command()
    def runjs(self, js):
        return self._tab.runjs(js)

    @command()
    def set_result_content_type(self, content_type):
        if not isinstance(content_type, basestring):
            raise ScriptError("splash:set_result_content_type() argument must be a string")
        self._result_content_type = content_type

    @command()
    def set_viewport(self, size):
        return self._tab.set_viewport(size)

    # TODO: hide from Lua using attribute filter
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
        # FIXME: cache file
        code = get_script_source("splash.lua")
        self._lua.execute(code)
        wrapper = self._lua.globals()["Splash"]
        return wrapper(self)

    def start_main(self, lua_source):
        """
        Start "main" function and return it as a coroutine.
        """
        return start_main(self._lua, lua_source, args=[self.get_wrapper()])

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
        self.log("[lua] dispatch %s" % (args,))

        while True:
            try:
                self.log("[lua] send %s" % (args,))
                command = self.coro.send(args or None)
                self.log("[lua] got %r" % command)
            except StopIteration:
                # previous result is a final result returned from "main"
                self.log("[lua] returning result")
                self.return_result(
                    (lua2python(self.result), self.splash.result_content_type())
                )
                return
            except lupa.LuaError as e:
                self.log("[lua] LuaError %r" % e)
                self.splash.raise_stored()
                # XXX: are Lua errors bad requests?
                raise ScriptError("unhandled Lua error: %s" % e)

            if isinstance(command, _AsyncCommand):
                self.log("[lua] executing %r" % command)
                meth = getattr(self.tab, command.name)
                meth(**command.kwargs)
                return
            else:
                self.log("[lua] got non-command")
                self.result = command

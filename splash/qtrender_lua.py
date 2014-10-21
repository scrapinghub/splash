# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import functools
import inspect
from collections import namedtuple
import lupa
from splash.qtrender import RenderScript, RenderError, stop_on_error
from splash.lua import (
    table_as_kwargs,
    table_as_kwargs_method,
    is_lua_table,
    get_new_runtime,
    start_main
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


def command(func):
    """ Decorator for marking methods as commands available to Lua """
    func = table_as_kwargs_method(func)
    func._is_command = True
    return func


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
    _result_content_type = 'application/json'

    def __init__(self, tab, return_func, render_options):
        """
        :param splash.browser_tab.BrowserTab tab: BrowserTab object
        :param callable dispatch_func: function that continues the script
        """
        self._tab = tab
        self._return = return_func
        self._render_options = render_options
        self._exceptions = []

    @command
    @can_raise
    def wait(self, time, cancel_on_redirect=False):
        # TODO: it should return 'not_cancelled' flag
        return _AsyncCommand("wait", dict(
            time_ms=time*1000,
            callback=self._wait_success,
            onredirect=cancel_on_redirect,
        ))

    def _wait_success(self):
        self._return(True)

    @command
    @can_raise
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

    @command
    @can_raise
    def html(self):
        return self._tab.html()

    @command
    @can_raise
    def png(self, width=None, height=None, base64=False):
        return self._tab.png(width, height, b64=base64)

    @command
    @can_raise
    def har(self):
        return self._tab.har()

    @command
    @can_raise
    def history(self):
        return self._tab.history()

    @command
    @can_raise
    def stop(self):
        self._tab.stop_loading()

    @can_raise
    def set_result_content_type(self, content_type):
        if not isinstance(content_type, basestring):
            raise ScriptError("splash:set_result_content_type() argument must be a string")
        self._result_content_type = content_type



def lua2python(result):
    if is_lua_table(result):
        result = {
            lua2python(key): lua2python(value)
            for key, value in result.items()
        }
    elif isinstance(result, unicode):
        result = result.encode('utf8')
    return result



class LuaRender(RenderScript):

    default_min_log_level = 2
    result = ''

    @stop_on_error
    def start(self, lua_source):
        print(lua_source)
        self.lua = get_new_runtime()
        self.splash = Splash(self.tab, self.dispatch, self.render_options)
        try:
            self.coro = start_main(self.lua, lua_source, self.splash)
        except ValueError as e:
            raise BadOption("lua_source: " + str(e))
        self.dispatch()

    @stop_on_error
    def dispatch(self, *args):
        """ Execute the script """
        self.log("[lua] dispatch %s" % (args,))

        while True:
            try:
                self.log("[lua] send %s" % (args,))
                command = self.coro.send(args or None)
                # command = next(self.coro)
                self.log("[lua] got %r" % command)
            except StopIteration:
                # previous result is a final result returned from "main"
                self.log("[lua] returning result")
                self.return_result(
                    (lua2python(self.result), str(self.splash._result_content_type))
                )
                return
            except lupa.LuaError as e:
                self.log("[lua] LuaError %r" % e)
                if self.splash._exceptions:
                    raise self.splash._exceptions[-1]
                raise

            if isinstance(command, _AsyncCommand):
                self.log("[lua] executing %r" % command)
                meth = getattr(self.tab, command.name)
                meth(**command.kwargs)
                return
            else:
                self.log("[lua] got non-command")
                self.result = command

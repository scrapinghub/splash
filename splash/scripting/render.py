# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import functools
import inspect
from collections import namedtuple
import lupa
from splash.qtrender import RenderScript, RenderError, stop_on_error
from splash.scripting.lua import (
    table_as_kwargs,
    table_as_kwargs_method,
    is_lua_table,
    get_new_runtime,
    start_main
)


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


class Splash(object):
    """
    This object is passed to Lua script as an argument to 'main' function.
    """

    def __init__(self, tab, return_func):
        """
        :param splash.browser_tab.BrowserTab tab: BrowserTab object
        :param callable dispatch_func: function that continues the script
        """
        self._tab = tab
        self._return = return_func

    @command
    def wait(self, time, cancel_on_redirect=False):
        return _AsyncCommand("wait", dict(
            time_ms=time*1000,
            callback=self._wait_success,
            onredirect=cancel_on_redirect,
        ))

    def _wait_success(self):
        self._return(True)

    @command
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
    def html(self):
        return self._tab.html()

    @command
    def png(self, width=None, height=None, base64=False):
        return self._tab.png(width, height, b64=base64)

    @command
    def har(self):
        return self._tab.har()

    @command
    def history(self):
        return self._tab.history()

    @command
    def stop(self):
        self._tab.stop_loading()


class LuaRender(RenderScript):

    default_min_log_level = 3
    result = ''

    def _getscript(self):
        fn = os.path.join(os.path.dirname(__file__), 'scripts', 'tmp.lua')
        with open(fn, 'rb') as f:
            return f.read().decode('utf8')

    @stop_on_error
    def start(self, **kwarge):
        script = self._getscript()
        self.lua = get_new_runtime()
        self.splash = Splash(self.tab, self.dispatch)
        self.coro = start_main(self.lua, script, self.splash)
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
                self.return_result(self.get_result())
                return
            except lupa.LuaError as e:
                self.log("[lua] LuaError")
                self.return_error(e)
                return

            if isinstance(command, _AsyncCommand):
                self.log("[lua] executing %r" % command)
                meth = getattr(self.tab, command.name)
                meth(**command.kwargs)
                return
            else:
                self.log("[lua] got non-command")
                self.result = command

    def get_result(self):
        result = self.result
        if is_lua_table(result):
            result = dict(result)
        elif isinstance(result, unicode):
            result = result.encode('utf8')
        elif isinstance(result, (int, long, float, bool)):
            result = str(result)
        return result

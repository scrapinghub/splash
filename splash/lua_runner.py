# -*- coding: utf-8 -*-
from __future__ import absolute_import
import abc

import lupa

from splash.render_options import BadOption
from splash.utils import truncated


class ImmediateResult(object):
    def __init__(self, value):
        self.value = value


class AsyncCommand(object):
    def __init__(self, id, name, kwargs):
        self.id = id
        self.name = name
        self.kwargs = kwargs


class ScriptError(BadOption):

    def enrich_from_lua_error(self, e):
        if not isinstance(e, lupa.LuaError):
            return

        print("enrich_from_lua_error", self, e)

        self_repr = repr(self.args[0])
        if self_repr in e.args[0]:
            self.args = (e.args[0],) + self.args[1:]
        else:
            self.args = (e.args[0] + "; " + self_repr,) + self.args[1:]


class BaseScriptRunner(object):
    """
    An utility class for running Lua coroutines.
    """
    __metaclass__ = abc.ABCMeta
    _START_CMD = '__START__'
    _waiting_for_result_id = None

    def __init__(self, lua, log, sandboxed):
        """
        :param splash.lua_runtime.SplashLuaRuntime lua: Lua runtime wrapper
        :param log: log function
        :param bool sandboxed: True if the execution should use sandbox
        """
        self.log = log
        self.sandboxed = sandboxed
        self.lua = lua

    def start(self, coro_func, coro_args):
        """
        Run the script.

        :param callable coro_func: Lua coroutine to start
        :param list coro_args: arguments to pass to coro_func
        """
        self.coro = coro_func(*coro_args)
        self.result = ''
        self._waiting_for_result_id = self._START_CMD
        self.dispatch(self._waiting_for_result_id)

    @abc.abstractmethod
    def on_result(self, result):
        """ This method is called when the coroutine exits. """
        pass

    @abc.abstractmethod
    def on_async_command(self, cmd):
        """ This method is called when AsyncCommand instance is received. """
        pass

    def on_lua_error(self, lua_exception):
        """
        This method is called when an exception happens in a Lua script.
        It is called with a lupa.LuaError instance and can raise a custom
        ScriptError.
        """
        pass

    def dispatch(self, cmd_id, *args):
        """ Execute the script """
        args_repr = truncated("{!r}".format(args), max_length=400, msg="...[long arguments truncated]")
        self.log("[lua] dispatch cmd_id={}, args={}".format(cmd_id, args_repr))

        self.log(
            "[lua] arguments are for command %s, waiting for result of %s" % (cmd_id, self._waiting_for_result_id),
            min_level=3,
        )
        if cmd_id != self._waiting_for_result_id:
            self.log("[lua] skipping an out-of-order result {}".format(args_repr), min_level=1)
            return

        while True:
            try:
                args = args or None

                # Got arguments from an async command; send them to coroutine
                # and wait for the next async command.
                self.log("[lua] send %s" % args_repr)
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
                    res = self.lua.lua2python(self.result)
                except ValueError as e:
                    # can't convert result to a Python object
                    raise ScriptError("'main' returned bad result. {!s}".format(e))

                self._print_instructions_used()
                self.on_result(res)
                return
            except lupa.LuaError as lua_ex:
                # Lua script raised an error
                self._print_instructions_used()
                self.log("[lua] caught LuaError %r" % lua_ex)
                self.on_lua_error(lua_ex)  # this can also raise a ScriptError

                # XXX: are Lua errors bad requests?
                raise ScriptError("unhandled Lua error: {!s}".format(lua_ex))

            if isinstance(cmd, AsyncCommand):
                self.log("[lua] executing {!r}".format(cmd))
                self._waiting_for_result_id = cmd.id
                self.on_async_command(cmd)
                return
            elif isinstance(cmd, ImmediateResult):
                self.log("[lua] got result {!r}".format(cmd))
                args = cmd.value
                continue
            else:
                self.log("[lua] got non-command")

                if isinstance(cmd, tuple):
                    cmd = list(cmd)

                self.result = cmd

    def _print_instructions_used(self):
        if self.sandboxed:
            self.log("[lua] instructions used: %d" % self.lua.instruction_count())


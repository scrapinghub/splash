# -*- coding: utf-8 -*-
from __future__ import absolute_import
import abc
import itertools

import lupa

from splash.exceptions import ScriptError
from splash.lua import parse_error_message
from splash.utils import truncated


class ImmediateResult(object):
    def __init__(self, value):
        self.value = value


class AsyncCommand(object):
    # Dispatcher should call .bind method to fill these attributes.
    dispatcher = None
    id = None

    def __init__(self, name, kwargs):
        self.name = name
        self.kwargs = kwargs

    def bind(self, dispatcher, id):
        self.dispatcher = dispatcher
        self.id = id

    def return_result(self, *args):
        """ Return result and resume the dispatcher. """
        self.dispatcher.dispatch(self.id, *args)


class BaseScriptRunner(object):
    """
    An utility class for running Lua coroutines.
    """
    __metaclass__ = abc.ABCMeta
    _START_CMD = '__START__'

    def __init__(self, lua, log, sandboxed):
        """
        :param splash.lua_runtime.SplashLuaRuntime lua: Lua runtime wrapper
        :param log: log function
        :param bool sandboxed: True if the execution should use sandbox
        """
        self.log = log
        self.sandboxed = sandboxed
        self.lua = lua
        self.coro = None
        self.result = None
        self._command_ids = itertools.count()
        self._waiting_for_result_id = None

    def start(self, coro_func, coro_args=None):
        """
        Run the script.

        :param callable coro_func: Lua coroutine to start
        :param list coro_args: arguments to pass to coro_func
        """
        self.coro = coro_func(*(coro_args or []))
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
        args = args or None
        args_repr = truncated("{!r}".format(args), max_length=400, msg="...[long arguments truncated]")
        self.log("[lua_runner] dispatch cmd_id={}, args={}".format(cmd_id, args_repr))

        self.log(
            "[lua_runner] arguments are for command %s, waiting for result of %s" % (cmd_id, self._waiting_for_result_id),
            min_level=3,
        )
        if cmd_id != self._waiting_for_result_id:
            self.log("[lua_runner] skipping an out-of-order result {}".format(args_repr), min_level=1)
            return

        while True:
            try:
                args = args or None

                # Got arguments from an async command; send them to coroutine
                # and wait for the next async command.
                self.log("[lua_runner] send %s" % args_repr)
                cmd = self.coro.send(args)  # cmd is a next async command

                args = None  # don't re-send the same value
                cmd_repr = truncated(repr(cmd), max_length=400, msg='...[long result truncated]')
                self.log("[lua_runner] got {}".format(cmd_repr))
                self._print_instructions_used()

            except StopIteration:
                # "main" coroutine is stopped;
                # previous result is a final result returned from "main"
                self.log("[lua_runner] returning result")
                try:
                    res = self.lua.lua2python(self.result)
                except ValueError as e:
                    # can't convert result to a Python object
                    raise ScriptError({
                        "type": ScriptError.BAD_MAIN_ERROR,
                        "message": "'main' returned bad result. {!s}".format(
                            e.args[0]
                        )
                    })

                self._print_instructions_used()
                self.on_result(res)
                return
            except lupa.LuaError as lua_ex:
                # Lua script raised an error
                self._print_instructions_used()
                self.log("[lua_runner] caught LuaError %r" % lua_ex)

                # this can raise a ScriptError
                self.on_lua_error(lua_ex)

                # ScriptError is not raised, construct it ourselves
                info = parse_error_message(lua_ex.args[0])
                info.update({
                    "type": ScriptError.LUA_ERROR,
                    "message": "Lua error: {!s}".format(lua_ex)
                })
                raise ScriptError(info)

            if isinstance(cmd, AsyncCommand):
                cmd.bind(self, next(self._command_ids))
                self.log("[lua_runner] executing {!r}".format(cmd))
                self._waiting_for_result_id = cmd.id
                self.on_async_command(cmd)
                return
            elif isinstance(cmd, ImmediateResult):
                self.log("[lua_runner] got result {!r}".format(cmd))
                args = cmd.value
                continue
            else:
                self.log("[lua_runner] got non-command")

                if isinstance(cmd, tuple):
                    cmd = list(cmd)

                self.result = cmd

    def _print_instructions_used(self):
        if self.sandboxed:
            self.log("[lua_runner] instructions used: %d" % self.lua.instruction_count())


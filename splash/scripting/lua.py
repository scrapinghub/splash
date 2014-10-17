# -*- coding: utf-8 -*-
from __future__ import absolute_import
import functools
from twisted.python import log

_supported = None
_lua = None


def is_supported():
    """ Return True if Lua scripting is supported """
    global _supported
    if _supported is not None:
        return _supported

    try:
        import lupa
    except ImportError:
        log.msg("WARNING: Lua scripting is not available because 'lupa' Python package is not installed")
        _supported = False
        return False

    try:
        lua = lupa.LuaRuntime()
    except lupa.LuaError as e:
        log.msg("WARNING: Lua scripting is not available: %r" % e)
        _supported = False
        return False

    _supported = True
    return True


def get_shared_runtime():
    """ Return a shared LuaRuntime instance, creating it if necessary. """
    import lupa
    global _lua
    if _lua is None:
        _lua = lupa.LuaRuntime()
    return _lua


def is_lua_table(obj):
    """
    Return True if obj is a wrapped LuaTable.

    >>> import lupa
    >>> lua = lupa.LuaRuntime()
    >>> is_lua_table(lua.eval("{foo='bar'}"))
    True
    >>> is_lua_table(lua.eval("123"))
    False
    >>> is_lua_table(lua.eval("function () end"))
    False

    """
    lua = get_shared_runtime()
    LuaTable = lua.eval("{}").__class__
    return isinstance(obj, LuaTable)


def get_version():
    """ Return Lua version """
    lua = get_shared_runtime()
    return lua.globals()["_VERSION"]


def _fix_args_kwargs(args):
    # lupa calls Python functions from Lua using args only;
    # convert them to kwargs if only one argument is passed and
    # it is a table.
    kwargs = {}
    if len(args) == 1 and is_lua_table(args[0]):
        kwargs = dict(args[0])
        args = []
    return args, kwargs


def table_as_kwargs(func):
    """
    A decorator to make decorated function receive kwargs
    when it is called from Lua with a single Lua table argument.

    It makes it possible to support both ``func(foo, bar)`` and
    ``func{foo=foo, bar=bar}`` in Lua code.

    WARNING: don't apply this decorator to functions which
    first argument can be a Lua table! For consistency it is better
    to avoid such functions in API.
    """
    def wrapper(*args):
        args, kwargs = _fix_args_kwargs(args)
        return func(*args, **kwargs)
    return functools.wraps(func)(wrapper)


def table_as_kwargs_method(func):
    """ This is :func:`table_as_kwargs` for methods. """
    def wrapper(self, *args):
        args, kwargs = _fix_args_kwargs(args)
        return func(self, *args, **kwargs)
    return functools.wraps(func)(wrapper)

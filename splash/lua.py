# -*- coding: utf-8 -*-
from __future__ import absolute_import
import functools
from twisted.python import log

_supported = None
_lua = None
_LuaTable = None
_LuaFunction = None


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
    Return True if obj is a wrapped Lua table.

    >>> import lupa
    >>> lua = lupa.LuaRuntime()
    >>> is_lua_table(lua.eval("{foo='bar'}"))
    True
    >>> is_lua_table(lua.eval("123"))
    False
    >>> is_lua_table(lua.eval("function () end"))
    False
    """
    global _LuaTable
    if _LuaTable is None:
        lua = get_shared_runtime()
        _LuaTable = lua.eval("{}").__class__
    return isinstance(obj, _LuaTable)


def is_lua_function(obj):
    """
    Return True if obj is a wrapped Lua function.

    >>> import lupa
    >>> lua = lupa.LuaRuntime()
    >>> is_lua_table(lua.eval("{foo='bar'}"))
    False
    >>> is_lua_table(lua.eval("123"))
    False
    >>> is_lua_table(lua.eval("function () end"))
    True
    """
    global _LuaFunction
    if _LuaFunction is None:
        lua = get_shared_runtime()
        _LuaFunction = lua.eval("function() end").__class__
    return isinstance(obj, _LuaFunction)


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


def get_new_runtime():
    """ Return a pre-configured LuaRuntime. """
    # TODO: sandboxing.
    import lupa
    return lupa.LuaRuntime(
        encoding=None,
        register_eval=False,
        unpack_returned_tuples=True,
    )


def _get_entrypoint(lua, script):
    """
    Execute a script and return its "main" function.

    >>> import lupa; lua = lupa.LuaRuntime()
    >>> main = _get_entrypoint(lua, "x=1; function main() return 55 end")
    >>> main()
    55
    """
    lua.execute(script)
    return lua.globals()["main"]


def start_main(lua, script, *args):
    """
    Start "main" coroutine and pass args to it.
    Return the started coroutine.
    """
    main = _get_entrypoint(lua, script)
    if main is None:
        raise ValueError("'main' function is not found")
    if not is_lua_function(main):
        raise ValueError("'main' is not a function")
    return main.coroutine(*args)

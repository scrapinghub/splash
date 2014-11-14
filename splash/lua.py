# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import functools
import datetime
from twisted.python import log
try:
    import lupa
except ImportError:
    lupa = None

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
    global _lua
    if _lua is None:
        _lua = lupa.LuaRuntime()
    return _lua


def get_version():
    """ Return Lua version """
    lua = get_shared_runtime()
    return lua.globals()["_VERSION"]


def _fix_args_kwargs(args):
    # lupa calls Python functions from Lua using args only;
    # convert them to kwargs if only one argument is passed and
    # it is a table.
    kwargs = {}
    if len(args) == 1 and lupa.lua_type(args[0]) == 'table':
        table = args[0]
        args = [table[key] for key in range(1, len(table)+1)]
        kwargs = {
            key: value for key, value in table.items()
            if not isinstance(key, int)
        }
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


def get_new_runtime(**kwargs):
    """ Return a pre-configured LuaRuntime. """
    kwargs.setdefault('register_eval', False)
    kwargs.setdefault('unpack_returned_tuples', True)
    lua = lupa.LuaRuntime(**kwargs)
    lua.execute("assert(os.setlocale('C'))")
    return lua


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


def start_main(lua, script, args):
    """
    Start "main" coroutine and pass args to it.
    Return the started coroutine.
    """
    main = _get_entrypoint(lua, script)
    if main is None:
        raise ValueError("'main' function is not found")
    if lupa.lua_type(main) != 'function':
        raise ValueError("'main' is not a function")
    return main.coroutine(*args)


def get_script_source(name):
    """ Return contents of a file from /scripts folder """
    filename = os.path.join(os.path.dirname(__file__), "scripts", name)
    with open(filename, 'rb') as f:
        return f.read().decode('utf8')


def lua2python(lua, obj, binary=True, strict=True, max_depth=100):
    """ Recursively convert Lua data to Python objects """

    def l2p(obj, depth):
        if depth <= 0:
            raise ValueError("Can't convert Lua object to Python: depth limit is reached")

        if lupa.lua_type(obj) == 'table':
            if _is_table_a_list(lua, obj):
                res = []
                prev_key = 0
                for key, value in obj.items():
                    if not isinstance(key, int):
                        raise ValueError("Can't build a Python list from Lua table: invalid key %r" % key)
                    if key <= prev_key:
                        raise ValueError("Can't build a Python list from Lua table: bad index %s" % key)

                    res.extend([None] * (key-prev_key-1))
                    res.append(l2p(value, max_depth-1))
                    prev_key = key
                return res
            else:
                return {
                    l2p(key, max_depth-1): l2p(value, max_depth-1)
                    for key, value in obj.items()
                }

        if strict and lupa.lua_type(obj) is not None:
            raise ValueError(
                "Lua %s objects are not allowed." % lupa.lua_type(obj)
            )

        if binary and isinstance(obj, unicode):
            obj = obj.encode('utf8')

        return obj

    return l2p(obj, depth=max_depth)


def _mark_table_as_list(lua, tbl):
    mt = lua.table(__metatable="list")
    lua.eval("setmetatable")(tbl, mt)
    return tbl


def _is_table_a_list(lua, tbl):
    mt = lua.eval("getmetatable")(tbl)
    return mt == "list"


def python2lua(lua, obj, max_depth=100):
    """
    Recursively convert Python object to a Lua data structure.
    Parts that can't be converted to Lua types are passed as-is.

    For Lua runtimes with restrictive attribute filters it means such values
    are passed as "capsules" which Lua code can send back to Python as-is, but
    can't access otherwise.
    """
    if max_depth <= 0:
        raise ValueError("Can't convert Python object to Lua: depth limit is reached")

    if isinstance(obj, dict):
        return lua.table_from({
            python2lua(lua, key, max_depth-1): python2lua(lua, value, max_depth-1)
            for key, value in obj.iteritems()
        })

    if isinstance(obj, list):
        tbl = lua.table_from([python2lua(lua, el, max_depth-1) for el in obj])
        return _mark_table_as_list(lua, tbl)

    if isinstance(obj, unicode):
        # lupa encodes/decodes strings automatically,
        # but this doesn't apply to nested table keys.
        return obj.encode('utf8')

    if isinstance(obj, datetime.datetime):
        return obj.isoformat() + 'Z'
        # XXX: maybe return datetime encoded to Lua standard? E.g.:

        # tm = obj.timetuple()
        # return python2lua(lua, {
        #     '_jstype': 'Date',
        #     'year': tm.tm_year,
        #     'month': tm.tm_mon,
        #     'day': tm.tm_mday,
        #     'yday': tm.tm_yday,
        #     'wday': tm.tm_wday,  # fixme: in Lua Sunday is 1, in Python Monday is 0
        #     'hour': tm.tm_hour,
        #     'min': tm.tm_min,
        #     'sec': tm.tm_sec,
        #     'isdst': tm.tm_isdst,  # fixme: isdst can be -1 in Python
        # }, max_depth)

    return obj

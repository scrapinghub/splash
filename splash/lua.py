# -*- coding: utf-8 -*-
from __future__ import absolute_import, division
import os
import re
import functools
import datetime

from splash.utils import to_bytes, to_unicode
from twisted.python import log
try:
    import lupa
except ImportError:
    lupa = None
import six

from splash.exceptions import ScriptError

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
        _lua = lupa.LuaRuntime(encoding=None)
    return _lua


def get_version():
    """ Return Lua version """
    lua = get_shared_runtime()
    return lua.eval("_VERSION").decode('latin1')


def get_new_runtime(**kwargs):
    """ Return a pre-configured LuaRuntime. """
    kwargs.setdefault('register_eval', False)
    kwargs.setdefault('unpack_returned_tuples', True)
    kwargs.setdefault('encoding', None)
    lua = lupa.LuaRuntime(**kwargs)
    lua.execute("assert(os.setlocale('C'))")
    return lua


def get_main(lua, script):
    """
    Get "main" function and its global environment from a ``script``.
    """
    main = _get_entrypoint(lua, script)
    _check_main(main)
    return main, lua.eval("_G")


def get_main_sandboxed(lua, script):
    """
    Get "main" function and its (sandboxed) global environment
    from a ``script``.
    """
    env = run_in_sandbox(lua, script)
    main = env[b"main"]
    _check_main(main)
    return main, env


def run_in_sandbox(lua, script):
    """
    Execute ``script`` in ``lua`` runtime using "sandbox" Lua module.
    Return a (sandboxed) global environment for the executed script.

    "sandbox" module should be importable in the environment.
    It should provide ``sandbox.run(untrusted_code)`` method and
    ``sandbox.env`` table with a global environment.
    See ``splash/lua_modules/sandbox.lua``.
    """
    sandbox = lua.eval("require('sandbox')")
    result = sandbox.run(to_bytes(script))
    if result is not True:
        ok, res = result
        raise lupa.LuaError(res)
    return sandbox.env


def _get_entrypoint(lua, script):
    """
    Execute a script and return its "main" function.

    >>> import lupa; lua = lupa.LuaRuntime()
    >>> main = _get_entrypoint(lua, "x=1; function main() return 55 end")
    >>> main()
    55
    """
    lua.execute(to_bytes(script))
    return lua.eval("main")


def _check_main(main):
    if main is None:
        raise ScriptError({
            "type": ScriptError.MAIN_NOT_FOUND_ERROR,
            "message": "'main' function is not found",
        })
    if lupa.lua_type(main) != 'function':
        raise ScriptError({
            "type": ScriptError.BAD_MAIN_ERROR,
            "message": "'main' is not a function",
        })


def lua2python(lua, obj, encoding='utf-8', strict=True, max_depth=100, sparse_limit=10):
    """
    Recursively convert Lua ``obj`` to Python objects.

    When ``encoding`` is None, binary data is not decoded to unicode;
    otherwise it is decoded using this encoding.

    When ``strict`` is True, lua2python raises an exception for Lua objects
    which can't be converted to Python. When ``strict`` is False these objects
    are returned as lupa wrappers.
    """

    def l2p(obj, depth):
        if depth <= 0:
            raise ValueError("Can't convert Lua object to Python: depth limit is reached")

        if isinstance(obj, dict):
            return {
                l2p(key, depth-1): l2p(value, depth-1)
                for key, value in six.iteritems(obj)
            }

        if isinstance(obj, list):
            return [l2p(el, depth-1) for el in obj]

        if isinstance(obj, tuple):
            return tuple([l2p(el, depth-1) for el in obj])

        if isinstance(obj, set):
            return {l2p(el, depth-1) for el in obj}

        if lupa.lua_type(obj) == 'table':
            if _table_is_array(lua, obj):
                res = []
                prev_key = 0
                for key, value in obj.items():
                    if not isinstance(key, int):
                        raise ValueError("Can't build a Python list from Lua table: invalid key %r" % key)
                    if key <= prev_key:
                        raise ValueError("Can't build a Python list from Lua table: bad index %s" % key)

                    filler_size = key - prev_key - 1
                    if filler_size > sparse_limit:
                        raise ValueError("Lua table is too sparse. Try not to use nil values.")
                    res.extend([None] * filler_size)
                    res.append(l2p(value, depth-1))
                    prev_key = key
                return res
            else:
                return {
                    l2p(key, depth-1): l2p(value, depth-1)
                    for key, value in obj.items()
                }

        if strict and lupa.lua_type(obj) is not None:
            raise ValueError(
                "Lua %s objects are not allowed." % lupa.lua_type(obj)
            )

        if encoding is not None and isinstance(obj, bytes):
            obj = obj.decode(encoding)

        return obj

    return l2p(obj, depth=max_depth)


def _mark_table_as_array(lua, tbl):
    # XXX: the same function is available in Lua as treat.as_array.
    # XXX: if we want to add to a metatable instead of replacing it,
    # we must make sure metatable is not shared with other tables.
    mt = lua.table_from({b'__metatable': b'array'})
    lua.eval("setmetatable")(tbl, mt)
    return tbl


def _table_is_array(lua, tbl):
    mt = lua.eval("getmetatable")(tbl)
    return mt == b"array"


def python2lua(lua, obj, max_depth=100, encoding='utf8', keep_tuples=True):
    """
    Recursively convert Python object to a Lua data structure.
    Parts that can't be converted to Lua types are passed as-is.

    For Lua runtimes with restrictive attribute filters it means such values
    are passed as "capsules" which Lua code can send back to Python as-is, but
    can't access otherwise.
    """

    def p2l(obj, depth):
        if depth <= 0:
            raise ValueError("Can't convert Python object to Lua: depth limit is reached")

        if isinstance(obj, PyResult):
            return tuple(p2l(elt, depth-1) for elt in obj.result)

        if isinstance(obj, dict):
            return lua.table_from({
                p2l(key, depth-1): p2l(value, depth-1)
                for key, value in six.iteritems(obj)
            })

        if isinstance(obj, tuple) and keep_tuples:
            return tuple(p2l(el, depth-1) for el in obj)

        if isinstance(obj, (list, tuple)):
            tbl = lua.table_from([p2l(el, depth-1) for el in obj])
            return _mark_table_as_array(lua, tbl)

        if isinstance(obj, six.text_type):
            return obj.encode(encoding)

        if isinstance(obj, datetime.datetime):
            return to_bytes(obj.isoformat() + 'Z', encoding)
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

    return p2l(obj, depth=max_depth)



_SYNTAX_ERROR_RE = re.compile(r'^error loading code: (\[string ".*?"\]):(\d+):\s+(.+)$')
_LUA_ERROR_RE = re.compile(r'^(\[string\s+".*?"\]):(\d+):\s+(.*)$')

def parse_error_message(error_text):
    r"""
    Split Lua error message into 'source', 'line_number' and 'error'.
    If error message can't be parsed, an empty dict is returned.

    This function is not reliable because error text is ambiguous.

    Parse runtime error messages::

        >>> info = parse_error_message('[string "function main(splash)\r..."]:2: /app/splash.lua:81: ValueError(\'could not convert string to float: sdf\'')
        >>> print(info['line_number'])
        2
        >>> print(repr(info['source']))
        '[string "function main(splash)\r..."]'
        >>> print(info['error'])
        /app/splash.lua:81: ValueError('could not convert string to float: sdf'

        >>> parse_error_message('dfsadf')
        {}

    Parse syntax errors::

        >>> info = parse_error_message("error loading code: [string \"<python>\"]:1: syntax error near 'ction'")
        >>> info['line_number']
        1
        >>> print(info['error'])
        syntax error near 'ction'

    """
    error_text = to_unicode(error_text)
    m = _LUA_ERROR_RE.match(error_text)
    if not m:
        m = _SYNTAX_ERROR_RE.match(error_text)

    if not m:
        return {}

    return {
        'source': m.group(1),
        'line_number': int(m.group(2)),
        'error': m.group(3)
    }


class PyResult(object):
    """Representation of Python operation result.

    Usage::

       return PyResult('foo', 'bar')  # same as PyResult.return_('foo', 'bar')

       return PyResult.yield_(AsyncResult())

       return PyResult.raise_('errmsg')

    There are three ways the result might be handled in Lua (carried out by
    wraputils:unwrap_python_result):

    - ``PyResult(*args)`` (or ``PyResult.return_(*args)``)

      Passes args as return values to Lua interpreter.  It is the default, so
      you can write ``PyResult([ arg1, ... ])`` too.

    - ``PyResult.raise_(error)``

      Raises an error in Lua interpreter.

    - ``PyResult.yield_(*args)``

      Passes args asynchronously to Lua interpreter via ``coroutine.yield``

    """
    def __init__(self, *result, **kwargs):
        operation = kwargs.get('_operation', 'return')
        if operation not in ('return', 'raise', 'yield'):
            raise ValueError('Invalid PyResult operation: %r' % operation)
        self.result = (operation,) + result

    def __repr__(self):
        return '%s(%s)' % (type(self).__name__,
                           ', '.join(repr(x) for x in self.result))

    @staticmethod
    def raise_(error):
        return PyResult(error, _operation='raise')

    @staticmethod
    def return_(*args):
        return PyResult(*args, _operation='return')

    @staticmethod
    def yield_(*args):
        return PyResult(*args, _operation='yield')

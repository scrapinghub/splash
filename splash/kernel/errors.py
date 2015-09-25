# -*- coding: utf-8 -*-
from __future__ import absolute_import
import lupa

from splash.exceptions import ScriptError
from splash.lua import parse_error_message


def error_repr(e):
    """
    Return repr of an exception, for printing as a cell execution result.
    """
    if isinstance(e, (ScriptError, lupa.LuaSyntaxError, lupa.LuaError)):
        if isinstance(e, ScriptError):
            info = e.args[0]
            tp = info['type']
        else:
            info = parse_error_message(e.args[0])
            tp = ScriptError.SYNTAX_ERROR
        line_num = info.get('line_number', -1)
        message = info.get('error', info.get('message'))
        return "%s [input]:%s: %s" % (tp, line_num, message)
    elif isinstance(e, Exception):
        return repr(e)
    return ScriptError.UNKNOWN_ERROR

# -*- coding: utf-8 -*-
from __future__ import absolute_import


class BadOption(Exception):
    """ Incorrect HTTP API arguments """
    pass


class RenderError(Exception):
    """ Error rendering page """
    pass


class InternalError(Exception):
    """ Unhandled internal error """
    pass


class GlobalTimeoutError(Exception):
    """ Timeout exceeded rendering page """
    pass


class UnsupportedContentType(Exception):
    """ Request Content-Type is not supported """
    pass


class ExpiredArguments(Exception):
    """ Arguments stored with ``save_args`` are expired """
    pass


class ScriptError(BadOption):
    """ Error happened while executing Lua script """
    LUA_INIT_ERROR = 'LUA_INIT_ERROR'  # error happened before coroutine starts
    LUA_ERROR = 'LUA_ERROR'  # lua error() is called from the coroutine
    LUA_CONVERT_ERROR = 'LUA_CONVERT_ERROR'  # result can't be converted to Python
    SPLASH_LUA_ERROR = 'SPLASH_LUA_ERROR'  # custom error raised by Splash
    BAD_MAIN_ERROR = 'BAD_MAIN_ERROR'  # main() definition is incorrect
    MAIN_NOT_FOUND_ERROR = 'MAIN_NOT_FOUND_ERROR'  # main() is not found
    SYNTAX_ERROR = 'SYNTAX_ERROR'  # XXX: unused; reported as INIT_ERROR now
    JS_ERROR = 'JS_ERROR'  # error in a wrapped JS function
    UNKNOWN_ERROR = 'UNKNOWN_ERROR'


class JsError(Exception):
    """ Error occured in JavaScript code """
    pass


class OneShotCallbackError(Exception):
    """ A one shot callback was called more than once. """
    pass


class DOMError(Exception):
    """ Error occurred during DOM operations"""
    NOT_IN_DOM_ERROR = 'NOT_IN_DOM_ERROR'
    NOT_COMPATIBLE_NODE_ERROR = 'NOT_COMPATIBLE_NODE_ERROR'

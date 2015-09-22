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

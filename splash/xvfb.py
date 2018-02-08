# -*- coding: utf-8 -*-
"""
Module for starting Xvfb automatically if it is available.
Uses xvfbwrapper Python package.
"""
import sys
from contextlib import contextmanager
from splash import defaults
from twisted.python import log


def autostart(disable=False, screen_size=None):
    if disable:
        return _dummy()
    return _get_xvfb(screen_size=screen_size) or _dummy()


def log_options(xvfb):
    if not hasattr(xvfb, 'xvfb_cmd'):  # dummy
        log.msg("Xvfb is not started automatically")
    else:
        log.msg("Xvfb is started: %s" % xvfb.xvfb_cmd)


@contextmanager
def _dummy():
    yield


def _get_xvfb(screen_size=None):
    if not sys.platform.startswith('linux'):
        return None

    try:
        from xvfbwrapper import Xvfb
        screen_size = screen_size or defaults.VIEWPORT_SIZE
        width, height = map(int, screen_size.split("x"))
        return Xvfb(width, height, nolisten="tcp")
    except ImportError:
        return None

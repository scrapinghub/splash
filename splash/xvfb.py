# -*- coding: utf-8 -*-
"""
Module for starting Xvfb automatically if it is available.
Uses xvfbwrapper Python package.
"""
from __future__ import absolute_import
import sys
from contextlib import contextmanager
from splash import defaults
from twisted.python import log


def autostart(disable=False):
    if disable:
        return _dummy()
    return _get_xvfb() or _dummy()


def log_options(xvfb):
    if not hasattr(xvfb, 'xvfb_cmd'):  # dummy
        log.msg("Xvfb is not started automatically")
    else:
        log.msg("Xvfb is started: %s" % xvfb.xvfb_cmd)


@contextmanager
def _dummy():
    yield


def _get_xvfb():
    if not sys.platform.startswith('linux'):
        return None

    try:
        from xvfbwrapper import Xvfb
        width, height = map(int, defaults.VIEWPORT_SIZE.split("x"))
        return Xvfb(width, height, nolisten="tcp")
    except ImportError:
        return None

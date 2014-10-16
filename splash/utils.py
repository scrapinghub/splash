from __future__ import absolute_import

import os
import gc
import sys
import json
import inspect
import resource
from collections import defaultdict
import psutil


_REQUIRED = object()


class BadRequest(Exception):
    pass


PID = os.getpid()
def get_num_fds():
    proc = psutil.Process(PID)
    return proc.get_num_fds()


def get_leaks():
    relevant_types = frozenset(('SplashQWebPage', 'SplashQNetworkAccessManager',
        'QWebView', 'HtmlRender', 'PngRender', 'JsonRender', 'HarRender',
        'QNetworkRequest', 'QSize', 'QBuffer', 'QPainter', 'QImage', 'QUrl',
        'JavascriptConsole', 'ProfilesSplashProxyFactory',
        'SplashProxyRequest', 'Request', 'Deferred'))
    leaks = defaultdict(int)
    gc.collect()
    for o in gc.get_objects():
        if not inspect.isclass(o):
            cname = type(o).__name__
            if cname in relevant_types:
                leaks[cname] += 1
    return leaks


def get_ru_maxrss():
    """ Return max RSS usage (in bytes) """
    size = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != 'darwin':
        # on Mac OS X ru_maxrss is in bytes, on Linux it is in KB
        size *= 1024
    return size

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


def getarg(request, name, default=_REQUIRED, type=str, range=None):
    """
    Return the value of argument named `name` from twisted.web.http.Request
    `request`. Argument can be GET argument, POST argument sent as form data
    or a value from a JSON dict if the request is a POST request with
    ``content-type: application/json``.
    """
    value = _getvalue(request, name)
    if value is not None:
        if type is not None:
            value = type(value)
        if range is not None and not (range[0] <= value <= range[1]):
            raise BadRequest("Argument %r out of range (%d-%d)" % (name, range[0], range[1]))
        return value
    elif default is _REQUIRED:
        raise BadRequest("Missing argument: %s" % name)
    else:
        return default


def getarg_bool(request, name, default=_REQUIRED):
    return getarg(request, name, default, type=int, range=(0, 1))


def _getvalue(request, name):
    value = request.args.get(name, [None])[0]
    if request.method == 'POST':
        content_type = request.getHeader('content-type')
        if content_type and 'application/json' in content_type:
            if not hasattr(request, '_json_data'):
                request._json_data = json.load(request.content, encoding='utf8') or {}
            return request._json_data.get(name, value)
    return value


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

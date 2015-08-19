from __future__ import absolute_import

import os
import gc
import sys
import json
import base64
import collections
import functools
import inspect
import resource
from collections import defaultdict
import psutil

import six

_REQUIRED = object()


class BadRequest(Exception):
    pass


class BinaryCapsule(object):
    """ A wrapper for passing binary data. """
    def __init__(self, data, content_type):
        self.data = data
        self.content_type = content_type

    def as_b64(self):
        return base64.b64encode(self.data).decode('utf-8')


class SplashJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, BinaryCapsule):
            return o.as_b64()
        return super(SplashJSONEncoder, self).default(o)


def bytes_to_unicode(data, encoding='utf-8'):
    """Recursively converts all bytes objects in object `data` to their unicode
    representation using the given encoding."""
    if isinstance(data, bytes):
        return data.decode(encoding)
    elif isinstance(data, dict):
        return dict(list(
            map(functools.partial(bytes_to_unicode, encoding=encoding),
                list(data.items()))))
    elif isinstance(data, (list, tuple)):
        return type(data)(list(
            map(functools.partial(bytes_to_unicode, encoding=encoding), data)))
    elif isinstance(data, BinaryCapsule):
        return bytes_to_unicode(data.as_b64())
    elif isinstance(data, (bool, six.integer_types, float, six.text_type)):
        return data
    else:
        raise TypeError('bytes_to_unicode expects bytes, str, unicode, list, '
                        'dict, tuple or %s object, got '
                        '%s' % (repr(BinaryCapsule), type(data).__name__))


def to_unicode(text, encoding=None, errors='strict'):
    """Return the unicode representation of a bytes object `text`. If `text`
    is already an unicode object, return it as-is."""
    if isinstance(text, six.text_type):
        return text
    if not isinstance(text, (bytes, six.text_type)):
        raise TypeError('to_unicode must receive a bytes, str or unicode '
                        'object, got %s' % type(text).__name__)
    if encoding is None:
        encoding = 'utf-8'
    return text.decode(encoding, errors)


def to_bytes(text, encoding=None, errors='strict'):
    """Return the binary representation of `text`. If `text`
    is already a bytes object, return it as-is."""
    if isinstance(text, bytes):
        return text
    if not isinstance(text, six.string_types):
        raise TypeError('to_bytes must receive a unicode, str or bytes '
                        'object, got %s' % type(text).__name__)
    if encoding is None:
        encoding = 'utf-8'
    return text.encode(encoding, errors)


PID = os.getpid()


def get_num_fds():
    proc = psutil.Process(PID)
    try:
        return proc.num_fds()
    except AttributeError:  # psutil < 2.0
        return proc.get_num_fds()


def get_alive():
    """ Return counts of alive objects. """
    relevant_types = frozenset(('SplashQWebPage', 'SplashQNetworkAccessManager',
                                'HtmlRender', 'PngRender', 'JsonRender',
                                'HarRender', 'LuaRender',
                                'QWebView', 'QWebPage', 'QWebFrame',
                                'QNetworkRequest', 'QNetworkReply',
                                'QNetworkProxy',
                                'QSize', 'QBuffer', 'QPainter', 'QImage',
                                'QUrl', 'QTimer',
                                'SplashCookieJar', 'OneShotCallbackProxy',
                                '_WrappedRequest', '_WrappedResponse',
                                'BrowserTab', '_SplashHttpClient',
                                'JavascriptConsole',
                                'ProfilesSplashProxyFactory',
                                'SplashProxyRequest', 'Request', 'Deferred',
                                'LuaRuntime', '_LuaObject', '_LuaTable',
                                '_LuaIter', '_LuaThread',
                                '_LuaFunction', '_LuaCoroutineFunction',
                                'LuaError', 'LuaSyntaxError',
                                ))
    counts = defaultdict(int)
    for o in gc.get_objects():
        if not inspect.isclass(o):
            cname = type(o).__name__
            if cname in relevant_types:
                counts[cname] += 1
    return dict(counts)


def get_leaks():
    gc.collect()
    return get_alive()


def get_ru_maxrss():
    """ Return max RSS usage (in bytes) """
    size = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != 'darwin':
        # on Mac OS X ru_maxrss is in bytes, on Linux it is in KB
        size *= 1024
    return size


def get_total_phymem():
    """ Return the total amount of physical memory available. """
    try:
        return psutil.virtual_memory().total
    except AttributeError:  # psutil < 2.0
        return psutil.phymem_usage().total


def truncated(text, max_length=100, msg='...'):
    """
    >>> truncated("hello world!", 5)
    'hello...'
    >>> truncated("hello world!", 25)
    'hello world!'
    >>> truncated("hello world!", 5, " [truncated]")
    'hello [truncated]'
    """
    if len(text) < max_length:
        return text
    else:
        return text[:max_length] + msg


def dedupe(it):
    """
    >>> list(dedupe([3,1,3,1,2]))
    [3, 1, 2]
    """
    seen = set()
    for el in it:
        if el in seen:
            continue
        seen.add(el)
        yield el

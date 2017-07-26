import os
import gc
import sys
import json
import base64
import inspect
import resource
from collections import defaultdict
import functools
import psutil
from uuid import uuid1


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

    # def __repr__(self):
    #     data_repr = truncated(repr(self.data), max_length=40)
    #     return "BinaryCapsule(%s, %r)" % (data_repr, self.content_type)


class SplashJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, BinaryCapsule):
            return o.as_b64()
        return super(SplashJSONEncoder, self).default(o)


def to_unicode(text, encoding=None, errors='strict'):
    """Return the unicode representation of a bytes object `text`. If `text`
    is already an unicode object, return it as-is."""
    if isinstance(text, str):
        return text
    if not isinstance(text, (bytes, str)):
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
    if not isinstance(text, str):
        raise TypeError('to_bytes must receive a str or bytes '
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
    relevant_types = {
        'SplashQWebPage', 'SplashQNetworkAccessManager',
        'HtmlRender', 'PngRender', 'JsonRender', 'HarRender', 'LuaRender',
        'QWebView', 'QWebPage', 'QWebFrame',
        'QNetworkRequest', 'QNetworkReply', 'QNetworkProxy',
        'QSize', 'QBuffer', 'QPainter', 'QImage', 'QUrl', 'QTimer',
        'SplashCookieJar', 'OneShotCallbackProxy',
        '_ExposedRequest', '_ExposedBoundRequest',
        '_ExposedResponse', '_ExposedBoundResponse',
        '_ExposedTimer',
        '_ExposedElement', '_ExposedElementStyle', '_ExposedEvent',
        'EventHandlersStorage', 'EventsStorage', ' ElementsStorage',
        'BrowserTab', '_SplashHttpClient', 'JavascriptConsole',
        'ProfilesSplashProxyFactory',
        'SplashProxyRequest', 'Request', 'Deferred',
        'LuaRuntime', '_LuaObject', '_LuaTable', '_LuaIter', '_LuaThread',
        '_LuaFunction', '_LuaCoroutineFunction', 'LuaError', 'LuaSyntaxError',
        'AsyncBrowserCommand',
    }
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


def path_join_secure(base, *paths):
    """
    Join two or more pathname components, inserting slashes as needed.
    Unlike os.path.join ValueError is raised if the result is
    outside ``base``.
    """
    base = os.path.abspath(base)
    if not base.endswith(os.path.sep):
        base = base + os.path.sep

    path = os.path.abspath(os.path.join(base, *paths))
    if not path.startswith(base):
        raise ValueError("Resulting path %r is outside %r." % (path, base))
    return path


def requires_attr(attr_name, raiser):
    """
    Methods wrapped in this decorator raise an error if a required
    attribute is not set.
    """
    def decorator(meth):
        @functools.wraps(meth)
        def wrapper(self, *args, **kwargs):
            if getattr(self, attr_name, None) is None:
                raiser(self, meth, attr_name)
            return meth(self, *args, **kwargs)
        return wrapper
    return decorator


def ensure_tuple(val):
    """If val is not a tuple, make it a 1-tuple containing val.

    This is useful for uniform processing of Lua output which can be either a
    single value or a tuple of values.

    """
    if not isinstance(val, tuple):
        return (val,)
    return val


def get_id():
    return str(uuid1())


def traverse_data(obj, predicate, convert, max_depth=100):
    """
    Traverse data structure and if the `predicate` returns True value on
    a traversed object call `convert` passing that object.
    """
    if max_depth <= 0:
        raise ValueError("Can't traverse through object: depth limit is reached")

    if obj is None:
        return None

    if predicate(obj):
        return convert(obj)

    if isinstance(obj, dict):
        return {
            traverse_data(key, predicate, convert, max_depth=max_depth - 1): traverse_data(value, predicate, convert, max_depth=max_depth - 1)
            for key, value in obj.items()
        }

    if isinstance(obj, list):
        return [
            traverse_data(v, predicate, convert, max_depth=max_depth - 1)
            for v in obj
        ]

    if isinstance(obj, tuple):
        return tuple([
            traverse_data(v, predicate, convert, max_depth=max_depth - 1)
            for v in obj
        ])

    if isinstance(obj, set):
        return {
            traverse_data(v, predicate, convert, max_depth=max_depth - 1)
            for v in obj
        }

    return obj

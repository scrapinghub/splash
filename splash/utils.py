import os, gc, inspect
from collections import defaultdict

_REQUIRED = object()

class BadRequest(Exception):
    pass

def getarg(request, name, default=_REQUIRED, type=str, range=None):
    if name in request.args:
        value = type(request.args[name][0])
        if range is not None and not (range[0] < value < range[1]):
            raise BadRequest("Argument %r out of range (%d-%d)" % (name, range[0], range[1]))
        return value
    elif default is _REQUIRED:
        raise BadRequest("Missing argument: %s" % name)
    else:
        return default

PID = os.getpid()
def get_num_fds():
    return len(os.listdir("/proc/%s/fd" % PID))

def get_leaks():
    relevant_types = frozenset(('SplashQWebPage', 'SplashQNetworkAccessManager',
        'QWebView', 'HtmlRender', 'PngRender', 'QNetworkRequest', 'QSize',
        'QBuffer', 'QPainter', 'QImage'))
    leaks = defaultdict(int)
    gc.collect()
    for o in gc.get_objects():
        if not inspect.isclass(o):
            cname = type(o).__name__
            if cname in relevant_types:
                leaks[cname] += 1
    return leaks

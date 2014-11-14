# -*- coding: utf-8 -*-
""" Utils for working with QWebKit objects.
"""
from __future__ import absolute_import
import sys
import time
import itertools
import functools

from twisted.python import log
from PyQt4.QtGui import QApplication
from PyQt4.QtCore import (
    QAbstractEventDispatcher, QVariant, QString, QObject,
    QDateTime, QRegExp
)
from PyQt4.QtCore import QUrl
from PyQt4.QtNetwork import QNetworkAccessManager

from splash.utils import truncated


OPERATION_NAMES = {
    QNetworkAccessManager.HeadOperation: 'HEAD',
    QNetworkAccessManager.GetOperation: 'GET',
    QNetworkAccessManager.PostOperation: 'POST',
    QNetworkAccessManager.PutOperation: 'PUT',
    QNetworkAccessManager.DeleteOperation: 'DELETE',
}
OPERATION_QT_CONSTANTS = {v:k for k,v in OPERATION_NAMES.items()}

# A global reference must be kept to QApplication, otherwise the process will
# segfault
_qtapp = None


def init_qt_app(verbose):
    """ Initialize Main Qt Application.
    :param verbose:
    :return: QApplication
    """
    global _qtapp
    if _qtapp:
        log.msg("QApplication is already initiated.")
        return _qtapp

    class QApp(QApplication):

        blockedAt = 0

        def __init__(self, *args):
            super(QApp, self).__init__(*args)
            if verbose:
                disp = QAbstractEventDispatcher.instance()
                disp.aboutToBlock.connect(self.aboutToBlock)
                disp.awake.connect(self.awake)

        def aboutToBlock(self):
            self.blockedAt = time.time()
            log.msg("aboutToBlock", system="QAbstractEventDispatcher")

        def awake(self):
            diff = time.time() - self.blockedAt
            log.msg("awake; block time: %0.4f" % diff, system="QAbstractEventDispatcher")
    _qtapp = QApp(sys.argv)
    return _qtapp


def get_qt_app():
    """ Return Main QtApplication. """
    assert _qtapp is not None, "init_qt_app should be called first."
    return _qtapp


def qurl2ascii(url):
    """ Convert QUrl to ASCII text suitable for logging """
    url = unicode(url.toString()).encode('unicode-escape').decode('ascii')
    if url.lower().startswith('data:'):
        return truncated(url, 80, '...[data uri truncated]')
    return url


def drop_request(request):
    """ Drop the request """
    # hack: set invalid URL
    request.setUrl(QUrl(''))


def request_repr(request, operation=None):
    """ Return string representation of QNetworkRequest suitable for logging """
    method = OPERATION_NAMES.get(operation, '?')
    url = qurl2ascii(request.url())
    return "%s %s" % (method, url)


def qt2py(obj, max_depth=100):
    """ Convert a QVariant object to a barebone non-PyQT object """

    if max_depth <= 0:
        raise ValueError("Can't convert object: depth limit is reached")

    if isinstance(obj, QVariant):
        obj = obj.toPyObject()

    # print(obj, obj.__class__)

    if isinstance(obj, QString):
        return unicode(obj)

    if isinstance(obj, QDateTime):
        return obj.toPyDateTime()

    if isinstance(obj, QRegExp):
        return {
            "_jstype": "RegExp",
            "pattern": unicode(obj.pattern()),
            "caseSensitive": bool(obj.caseSensitivity()),
        }

    if isinstance(obj, dict):
        return {
            qt2py(key, max_depth-1): qt2py(value, max_depth-1)
            for key, value in obj.items()
        }

    if isinstance(obj, list):
        return [qt2py(v, max_depth-1) for v in obj]

    if isinstance(obj, tuple):
        return tuple([qt2py(v, max_depth-1) for v in obj])

    if isinstance(obj, set):
        return {qt2py(v, max_depth-1) for v in obj}

    assert not isinstance(obj, QObject), (obj, obj.__class__)
    return obj


class WrappedSignal(object):
    """
    A wrapper for QT signals that assigns ids to callbacks,
    passes callback_id to the callback (as a keyword argument)
    and allows to disconnect callbacks by their ids.

    Its main purpose is to provide a way to disconnect a slot
    when callback is fired.
    """
    def __init__(self, signal):
        self.ids = itertools.count()
        self.callbacks = {}
        self.signal = signal

    def connect(self, func, **kwargs):
        callback_id = next(self.ids)
        cb = functools.partial(func, callback_id=callback_id, **kwargs)
        self.callbacks[callback_id] = cb
        self.signal.connect(cb)
        return callback_id

    def disconnect(self, callback_id):
        cb = self.callbacks.pop(callback_id)
        self.signal.disconnect(cb)

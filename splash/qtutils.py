# -*- coding: utf-8 -*-
""" Utils for working with QWebKit objects.
"""
from __future__ import absolute_import

import functools
import itertools
import re
import sys
import time

from PyQt5.QtCore import (QAbstractEventDispatcher, QDateTime, QObject,
                          QUrl, QVariant, QEvent, Qt, QByteArray)
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkProxy
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebFrame
from twisted.python import log
import six

from splash.utils import truncated, to_bytes


OPERATION_NAMES = {
    QNetworkAccessManager.HeadOperation: 'HEAD',
    QNetworkAccessManager.GetOperation: 'GET',
    QNetworkAccessManager.PostOperation: 'POST',
    QNetworkAccessManager.PutOperation: 'PUT',
    QNetworkAccessManager.DeleteOperation: 'DELETE',
}
OPERATION_QT_CONSTANTS = {v:k for k,v in OPERATION_NAMES.items()}


# See: http://pyqt.sourceforge.net/Docs/PyQt5/qnetworkreply.html#NetworkError-enum
REQUEST_ERRORS = {
    QNetworkReply.NoError : 'no error condition. Note: When the HTTP protocol returns a redirect no error will be reported. You can check if there is a redirect with the QNetworkRequest::RedirectionTargetAttribute attribute.',
    QNetworkReply.ConnectionRefusedError : 'the remote server refused the connection (the server is not accepting requests)',
    QNetworkReply.RemoteHostClosedError : 'the remote server closed the connection prematurely, before the entire reply was received and processed',
    QNetworkReply.HostNotFoundError : 'the remote host name was not found (invalid hostname)',
    QNetworkReply.TimeoutError : 'the connection to the remote server timed out',
    QNetworkReply.OperationCanceledError : 'the operation was canceled via calls to abort() or close() before it was finished.',
    QNetworkReply.SslHandshakeFailedError : 'the SSL/TLS handshake failed and the encrypted channel could not be established. The sslErrors() signal should have been emitted.',
    QNetworkReply.TemporaryNetworkFailureError : 'the connection was broken due to disconnection from the network, however the system has initiated roaming to another access point. The request should be resubmitted and will be processed as soon as the connection is re-established.',
    QNetworkReply.ProxyConnectionRefusedError : 'the connection to the proxy server was refused (the proxy server is not accepting requests)',
    QNetworkReply.ProxyConnectionClosedError : 'the proxy server closed the connection prematurely, before the entire reply was received and processed',
    QNetworkReply.ProxyNotFoundError : 'the proxy host name was not found (invalid proxy hostname)',
    QNetworkReply.ProxyTimeoutError : 'the connection to the proxy timed out or the proxy did not reply in time to the request sent',
    QNetworkReply.ProxyAuthenticationRequiredError : 'the proxy requires authentication in order to honour the request but did not accept any credentials offered (if any)',
    QNetworkReply.ContentAccessDenied : 'the access to the remote content was denied (similar to HTTP error 401)',
    QNetworkReply.ContentOperationNotPermittedError : 'the operation requested on the remote content is not permitted',
    QNetworkReply.ContentNotFoundError : 'the remote content was not found at the server (similar to HTTP error 404)',
    QNetworkReply.AuthenticationRequiredError : 'the remote server requires authentication to serve the content but the credentials provided were not accepted (if any)',
    QNetworkReply.ContentReSendError : 'the request needed to be sent again, but this failed for example because the upload data could not be read a second time.',
    QNetworkReply.ProtocolUnknownError : 'the Network Access API cannot honor the request because the protocol is not known',
    QNetworkReply.ProtocolInvalidOperationError : 'the requested operation is invalid for this protocol',
    QNetworkReply.UnknownNetworkError : 'an unknown network-related error was detected',
    QNetworkReply.UnknownProxyError : 'an unknown proxy-related error was detected',
    QNetworkReply.UnknownContentError : 'an unknown error related to the remote content was detected',
    QNetworkReply.ProtocolFailure : 'a breakdown in protocol was detected (parsing error, invalid or unexpected responses, etc.)',
}

REQUEST_ERRORS_SHORT = {
    QNetworkReply.NoError: 'OK',
    QNetworkReply.OperationCanceledError: 'cancelled',
    QNetworkReply.ConnectionRefusedError: 'connection_refused',
    QNetworkReply.RemoteHostClosedError : 'connection_closed',
    QNetworkReply.HostNotFoundError : 'invalid_hostname',
    QNetworkReply.TimeoutError : 'timed_out',
    QNetworkReply.SslHandshakeFailedError : 'ssl_error',
    QNetworkReply.TemporaryNetworkFailureError : 'temp_network_failure',
    QNetworkReply.ProxyConnectionRefusedError : 'proxy_connection_refused',
    QNetworkReply.ProxyConnectionClosedError : 'proxy_connection_closed',
    QNetworkReply.ProxyNotFoundError : 'proxy_not_found',
    QNetworkReply.ProxyTimeoutError : 'proxy_timeout',
    QNetworkReply.ProxyAuthenticationRequiredError : 'proxy_auth_required',
    QNetworkReply.ContentAccessDenied : 'access_denied_401',
    QNetworkReply.ContentOperationNotPermittedError : 'operation_not_permitted',
    QNetworkReply.ContentNotFoundError : 'not_found_404',
    QNetworkReply.AuthenticationRequiredError : 'auth_required',
    QNetworkReply.ContentReSendError : 'must_resend',
    QNetworkReply.ProtocolUnknownError : 'unknown_protocol',
    QNetworkReply.ProtocolInvalidOperationError : 'invalid_operation',
    QNetworkReply.UnknownNetworkError : 'unknown_network_error',
    QNetworkReply.UnknownProxyError : 'unknown_proxy_error',
    QNetworkReply.UnknownContentError : 'unknown_remote_content_error',
    QNetworkReply.ProtocolFailure : 'protocol_error',
}

PROXY_TYPES = {
    'HTTP': QNetworkProxy.HttpProxy,
    'SOCKS5': QNetworkProxy.Socks5Proxy,
}

# Qt key types mapped to the input they generate
QT_KEY_INPUTS = {
    # TODO: More needed?
    Qt.Key_Return: '\r',
    Qt.Key_Enter: '\r',
    Qt.Key_Space: ' ',
    Qt.Key_Tab: '\t',
    Qt.Key_Delete: chr(127),
}

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
    url = six.text_type(url.toString()).encode('unicode-escape').decode('ascii')
    if url.lower().startswith('data:'):
        return truncated(url, 80, '...[data uri truncated]')
    return url


def to_qurl(s):
    if isinstance(s, QUrl):
        return s
    return QUrl.fromEncoded(to_bytes(s, encoding='utf8'))


def qt_to_bytes(value):
    """ Convert QByteArray to bytes; if object is already a bytes object then
    pass it as-is. """
    if isinstance(value, QByteArray):
        value = bytes(value)
    if not isinstance(value, bytes):
        raise ValueError("Value must be bytes, got %s object instead",
                         value.__class__.__name__)
    return value


def set_request_url(request, url):
    """ Set an URL for a QNetworkRequest """
    request.setUrl(to_qurl(url))


def drop_request(request):
    """ Drop the request """
    set_request_url(request, "")  # hack: set invalid URL


def validate_proxy_type(typename):
    if typename.upper() not in PROXY_TYPES:
        alllowed = ", ".join(PROXY_TYPES.keys())
        raise ValueError(
            "Invalid proxy type %r. Allowed values: %s" % (typename, alllowed)
        )


def create_proxy(host, port, username=None, password=None, type=None):
    """ Create a new QNetworkProxy object """
    if type is None:
        type = 'HTTP'
    validate_proxy_type(type)
    proxy_type = PROXY_TYPES[type.upper()]
    port = int(port)
    if username is not None and password is not None:
        proxy = QNetworkProxy(proxy_type, host, port, username, password)
    else:
        proxy = QNetworkProxy(proxy_type, host, port)
    return proxy


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

    if isinstance(obj, QDateTime):
        return obj.toPyDateTime()

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


def clear_caches():
    QWebSettings.clearMemoryCaches()


def get_request_webframe(request):
    """ Return a QWebFrame which sent this QNetworkRequest """
    web_frame = request.originatingObject()
    if isinstance(web_frame, QWebFrame):
        return web_frame
    return None


def get_versions():
    """ Return a dictionary with qt/pyqt/webkit/sip versions """
    from sip import SIP_VERSION_STR
    from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
    from PyQt5.QtWebKit import qWebKitVersion

    return {
        'qt': QT_VERSION_STR,
        'pyqt': PYQT_VERSION_STR,
        'webkit': qWebKitVersion(),
        'sip': SIP_VERSION_STR
    }


def qt_551_plus():
    """ Return True if Qt version is 5.5.1+ """
    from distutils.version import LooseVersion
    from PyQt5.QtCore import QT_VERSION_STR
    return LooseVersion(QT_VERSION_STR) >= LooseVersion("5.5.1")


def get_headers_dict(request_or_reply):
    """ Return a dict with headers, without any Qt data types """
    return {bytes(k): bytes(v) for k, v in qt_header_items(request_or_reply)}


def qt_header_items(request_or_reply):
    """
    Return a list of (name, value) tuples with QNetworkRequest or
    QNetworkReply headers.
    """
    # rawHeaderPairs is O(N), but it is only available for QNetworkReply
    if hasattr(request_or_reply, 'rawHeaderPairs'):
        return request_or_reply.rawHeaderPairs()

    # rawHeaderList+rawHeader is O(N^2), but available both for
    # QNetworkReply and QNetworkRequest
    return [
        (name, request_or_reply.rawHeader(name))
        for name in request_or_reply.rawHeaderList()
    ]


def qt_send_key(key, target):
    """
    Send a key event that might be defined using emacs keyboard macro syntax
    to target qt object. For example:
        - <Space> -> Qt.Key_Space
        - <FooBar> -> Qt.Key_FooBar
    See: http://doc.qt.io/qt-5/qt.html#Key-enum for valid key types
    """

    # Try to match "<Key_Name>"
    key_match = re.match(r'^<(\w+)\>$', key)
    if key_match:
        key_type = getattr(Qt, 'Key_%s' % key_match.group(1), None)
        if not key_type:
            raise ValueError('Unknown key: %s' % key_match.group(1))
        text = QT_KEY_INPUTS.get(key_type, '')
        return qt_send_text(text, target, key_type)

    # All above failed, send as fallback input
    return qt_send_text(key, target)


def qt_send_text(text, target, key_type=0):
    """
    Send text as key input event to target qt object, as if generated by
    `key_type`. Key type defaults to 0, meaning "the event is not a result of a
    known key; for example, it may be the result of a compose sequence or
    keyboard macro."
    """
    modifiers = QApplication.keyboardModifiers()
    text = list(text) or ['']
    for x in text:
        event = QKeyEvent(QEvent.KeyPress, key_type, modifiers, x)
        QApplication.postEvent(target, event)
        # Key release does not generate any input
        event = QKeyEvent(QEvent.KeyRelease, key_type, modifiers, '')
        QApplication.postEvent(target, event)

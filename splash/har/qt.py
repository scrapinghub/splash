# -*- coding: utf-8 -*-
"""
Module with helper utilities to serialize QWebkit objects to HAR.
See http://www.softwareishard.com/blog/har-12-spec/.
"""
from __future__ import absolute_import

from PyQt4.QtCore import Qt
from PyQt4.QtNetwork import QNetworkRequest, QNetworkReply


ERRORS_SHORT = {
    QNetworkReply.NoError: 'OK',
    QNetworkReply.OperationCanceledError: 'cancelled',
    QNetworkReply.ConnectionRefusedError: 'connection_refused',
    QNetworkReply.RemoteHostClosedError : 'connection_closed',
    QNetworkReply.HostNotFoundError : 'invalid_hostname',
    QNetworkReply.TimeoutError : 'timed_out',
    QNetworkReply.SslHandshakeFailedError : 'ssl_error',
    QNetworkReply.TemporaryNetworkFailureError : 'temp_network_failure',
}


def _header_pairs(request_or_reply):
    if hasattr(request_or_reply, 'rawHeaderPairs'):
        return request_or_reply.rawHeaderPairs()
    return [
        (name, request_or_reply.rawHeader(name))
        for name in request_or_reply.rawHeaderList()
    ]


def headers2har(request_or_reply):
    """ Return HAR-encoded request or reply headers """
    return [
        {
            "name": bytes(name).decode('latin1'),
            "value": bytes(value).decode('latin1'),
        }
        for name, value in _header_pairs(request_or_reply)
    ]


def headers_size(request_or_reply):
    """ Return the total size of request or reply headers. """
    # XXX: this is not 100% correct, but should be a good approximation.
    size = 0
    for name, value in _header_pairs(request_or_reply):
        size += name.size() + 2 + value.size() + 2  # 2==len(": ")==len("\n\r")
    return size


def request_cookies2har(request):
    """ Return HAR-encoded cookies of QNetworkRequest """
    cookies = request.header(QNetworkRequest.CookieHeader)
    return _cookies2har(cookies)


def reply_cookies2har(reply):
    """ Return HAR-encoded cookies of QNetworkReply """
    cookies = reply.header(QNetworkRequest.SetCookieHeader)
    return _cookies2har(cookies)


def _cookies2har(cookies):
    cookies = cookies.toPyObject() or []
    return [
        {
            "name": bytes(cookie.name()),
            "value": bytes(cookie.value()),
            "path": unicode(cookie.path()),
            "domain": unicode(cookie.domain()),
            "expires": unicode(cookie.expirationDate().toString(Qt.ISODate)),
            "httpOnly": cookie.isHttpOnly(),
            "secure": cookie.isSecure(),
        }
        for cookie in cookies
    ]


def querystring2har(url):
    return [
        {"name": unicode(name), "value": unicode(value)}
        for name, value in url.queryItems()
    ]


def reply2har(reply):
    """ Serialize QNetworkReply to HAR. """
    res = {
        "httpVersion": "HTTP/1.1",  # XXX: how to get HTTP version?
        "cookies": reply_cookies2har(reply),
        "headers": headers2har(reply),
        "content": {
            "size": 0,
            "mimeType": "",
        },
        "headersSize" : headers_size(reply),
    }

    content_type = reply.header(QNetworkRequest.ContentTypeHeader)
    if not content_type.isNull():
        res["content"]["mimeType"] = unicode(content_type.toString())

    content_length = reply.header(QNetworkRequest.ContentLengthHeader)
    if not content_length.isNull():
        # this is not a correct way to get the size!
        res["content"]["size"] = content_length.toInt()[0]

    status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
    if not status.isNull():
        status, ok = status.toInt()
        res["status"] = int(status)
    else:
        res["status"] = 0

    status_text = reply.attribute(QNetworkRequest.HttpReasonPhraseAttribute)
    if not status_text.isNull():
        res["statusText"] = bytes(status_text.toByteArray()).decode('latin1')
    else:
        res["statusText"] = ERRORS_SHORT.get(reply.error(), "?")

    redirect_url = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
    if not redirect_url.isNull():
        res["redirectURL"] = unicode(redirect_url.toString())
    else:
        res["redirectURL"] = ""

    # res2 = res.copy()
    # del res2["headers"]
    # print(res2)

    return res

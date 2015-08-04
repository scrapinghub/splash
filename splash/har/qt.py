# -*- coding: utf-8 -*-
"""
Module with helper utilities to serialize QWebkit objects to HAR.
See http://www.softwareishard.com/blog/har-12-spec/.
"""
from __future__ import absolute_import
import base64

from PyQt4.QtCore import Qt, QVariant
from PyQt4.QtNetwork import QNetworkRequest

from splash.qtutils import REQUEST_ERRORS_SHORT, OPERATION_NAMES


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
    return cookies2har(cookies)


def reply_cookies2har(reply):
    """ Return HAR-encoded cookies of QNetworkReply """
    cookies = reply.header(QNetworkRequest.SetCookieHeader)
    return cookies2har(cookies)


def cookies2har(cookies):
    """ Convert QList<QNetworkCookie> to HAR format """
    if isinstance(cookies, QVariant):
        cookies = cookies.toPyObject()
    return [cookie2har(cookie) for cookie in (cookies or [])]


def cookie2har(cookie):
    """ Convert QNetworkCookie to a Python dict (in HAR format) """
    cookie = {
        "name": bytes(cookie.name()),
        "value": bytes(cookie.value()),
        "path": unicode(cookie.path()),
        "domain": unicode(cookie.domain()),
        "expires": unicode(cookie.expirationDate().toString(Qt.ISODate)),
        "httpOnly": cookie.isHttpOnly(),
        "secure": cookie.isSecure(),
    }
    if not cookie["expires"]:
        del cookie["expires"]
    return cookie


def querystring2har(url):
    return [
        {"name": unicode(name), "value": unicode(value)}
        for name, value in url.queryItems()
    ]


def reply2har(reply, include_content=False, binary_content=False):
    """ Serialize QNetworkReply to HAR. """
    res = {
        "httpVersion": "HTTP/1.1",  # XXX: how to get HTTP version?
        "cookies": reply_cookies2har(reply),
        "headers": headers2har(reply),
        "content": {
            "size": 0,
            "mimeType": "",
        },
        "headersSize": headers_size(reply),
        # non-standard but useful
        "ok": not reply.error(),
        # non-standard, useful because reply url may not equal request url
        # in case of redirect
        "url": unicode(reply.url().toString())
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
        res["statusText"] = REQUEST_ERRORS_SHORT.get(reply.error(), "?")

    redirect_url = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
    if not redirect_url.isNull():
        res["redirectURL"] = unicode(redirect_url.toString())
    else:
        res["redirectURL"] = ""

    if include_content:
        data = bytes(reply.readAll())
        if binary_content:
            res["content"]["encoding"] = "binary"
            res["content"]["text"] = data
            res["content"]["size"] = len(data)
        else:
            res["content"]["encoding"] = "base64"
            res["content"]["text"] = base64.b64encode(data)
            res["content"]["size"] = len(data)

    return res


def request2har(request, operation, outgoing_data=None):
    """ Serialize QNetworkRequest to HAR. """
    return {
        "method": OPERATION_NAMES.get(operation, '?'),
        "url": unicode(request.url().toString()),
        "httpVersion": "HTTP/1.1",
        "cookies": request_cookies2har(request),
        "queryString": querystring2har(request.url()),
        "headers": headers2har(request),
        "headersSize": headers_size(request),
        "bodySize": outgoing_data.size() if outgoing_data is not None else -1,
    }

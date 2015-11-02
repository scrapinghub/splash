# -*- coding: utf-8 -*-
"""
Module with helper utilities to serialize QWebkit objects to HAR.
See http://www.softwareishard.com/blog/har-12-spec/.
"""
from __future__ import absolute_import
import base64

from PyQt5.QtCore import Qt, QVariant, QUrlQuery
from PyQt5.QtNetwork import QNetworkRequest
import six

from splash.qtutils import (
    REQUEST_ERRORS_SHORT,
    OPERATION_NAMES,
    qt_header_items
)


def headers2har(request_or_reply):
    """ Return HAR-encoded request or reply headers """
    return [
        {
            "name": bytes(name).decode('latin1'),
            "value": bytes(value).decode('latin1'),
        }
        for name, value in qt_header_items(request_or_reply)
    ]


def headers_size(request_or_reply):
    """ Return the total size of request or reply headers. """
    # XXX: this is not 100% correct, but should be a good approximation.
    size = 0
    for name, value in qt_header_items(request_or_reply):
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
        "name": bytes(cookie.name()).decode('utf8', 'replace'),
        "value": bytes(cookie.value()).decode('utf8', 'replace'),
        "path": six.text_type(cookie.path()),
        "domain": six.text_type(cookie.domain()),
        "expires": six.text_type(cookie.expirationDate().toString(Qt.ISODate)),
        "httpOnly": cookie.isHttpOnly(),
        "secure": cookie.isSecure(),
    }
    if not cookie["expires"]:
        del cookie["expires"]
    return cookie


def querystring2har(url):
    return [
        {"name": six.text_type(name), "value": six.text_type(value)}
        for name, value in QUrlQuery(url).queryItems()
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
        "url": reply.url().toString()
    }

    content_type = reply.header(QNetworkRequest.ContentTypeHeader)
    if content_type is not None:
        res["content"]["mimeType"] = six.text_type(content_type)

    content_length = reply.header(QNetworkRequest.ContentLengthHeader)
    if content_length is not None:
        # this is not a correct way to get the size!
        res["content"]["size"] = content_length

    status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
    if status is not None:
        res["status"] = int(status)
    else:
        res["status"] = 0

    status_text = reply.attribute(QNetworkRequest.HttpReasonPhraseAttribute)
    if status_text is not None:
        try:
            res["statusText"] = bytes(status_text, 'latin1').decode('latin1')
        except TypeError:
            res["statusText"] = bytes(status_text).decode('latin1')

    else:
        res["statusText"] = REQUEST_ERRORS_SHORT.get(reply.error(), "?")

    redirect_url = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
    if redirect_url is not None:
        res["redirectURL"] = six.text_type(redirect_url.toString())
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
        "url": six.text_type(request.url().toString()),
        "httpVersion": "HTTP/1.1",
        "cookies": request_cookies2har(request),
        "queryString": querystring2har(request.url()),
        "headers": headers2har(request),
        "headersSize": headers_size(request),
        "bodySize": outgoing_data.size() if outgoing_data is not None else -1,
    }

# -*- coding: utf-8 -*-
"""
Module with helper utilities to serialize QWebkit objects to HAR.
See http://www.softwareishard.com/blog/har-12-spec/.
"""
import base64

from PyQt5.QtCore import Qt, QVariant, QUrlQuery
from PyQt5.QtNetwork import QNetworkRequest

from splash.qtutils import (
    REQUEST_ERRORS_SHORT,
    OPERATION_NAMES,
    qt_header_items,
    qt_to_bytes,
)


def headers2har(request_or_reply):
    """ Return HAR-encoded request or reply headers """
    return [
        {
            "name": qt_to_bytes(name).decode('latin1'),
            "value": qt_to_bytes(value).decode('latin1'),
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
        "name": qt_to_bytes(cookie.name()).decode('utf8', 'replace'),
        "value": qt_to_bytes(cookie.value()).decode('utf8', 'replace'),
        "path": str(cookie.path()),
        "domain": str(cookie.domain()),
        "expires": str(cookie.expirationDate().toString(Qt.ISODate)),
        "httpOnly": cookie.isHttpOnly(),
        "secure": cookie.isSecure(),
    }
    if not cookie["expires"]:
        del cookie["expires"]
    return cookie


def querystring2har(url):
    return [
        {"name": str(name), "value": str(value)}
        for name, value in QUrlQuery(url).queryItems()
    ]


def reply2har(reply, content=None):
    """
    Serialize QNetworkReply to HAR.
    If ``content`` (a bytes object) is not None, 'content' field is filled.
    This function doesn't read reply to get the content because
    QNetworkReply content can be read only once.
    """
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
        res["content"]["mimeType"] = str(content_type)

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
        if not isinstance(status_text, str):
            status_text = qt_to_bytes(status_text).decode('latin1')
        res['statusText'] = status_text
    else:
        res["statusText"] = REQUEST_ERRORS_SHORT.get(reply.error(), "?")

    redirect_url = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
    if redirect_url is not None:
        res["redirectURL"] = str(redirect_url.toString())
    else:
        res["redirectURL"] = ""

    if content is not None:
        res["content"]["size"] = len(content)
        res["content"]["text"] = base64.b64encode(content).decode('latin1')
        res["content"]["encoding"] = 'base64'

    return res


def _har_postdata(body, content_type):
    """

    Build the postData value for HAR, from a binary body and a content type.

    """

    postdata = {"mimeType": content_type or "?"}

    if content_type == "application/x-www-form-urlencoded":
        # application/x-www-form-urlencoded is valid ASCII, see
        # <https://url.spec.whatwg.org/#concept-urlencoded-serializer>.
        try:
            postdata["text"] = body.decode('ascii')
        except UnicodeDecodeError:
            pass

    # This is non-standard. The HAR format does not specify how to handle
    # binary request data.
    if "text" not in postdata:
        postdata["encoding"] = "base64"
        postdata["text"] = base64.b64encode(body).decode('ascii')

    return postdata


def request2har(request, operation, content=None):
    """ Serialize QNetworkRequest to HAR. """
    har = {
        "method": OPERATION_NAMES.get(operation, '?'),
        "url": str(request.url().toString()),
        "httpVersion": "HTTP/1.1",
        "cookies": request_cookies2har(request),
        "queryString": querystring2har(request.url()),
        "headers": headers2har(request),
        "headersSize": headers_size(request),
        "bodySize": -1
    }
    if content is not None:
        har["bodySize"] = len(content)
        content_type = request.header(QNetworkRequest.ContentTypeHeader)
        har["postData"] = _har_postdata(content, content_type)
    else:
        content_length = request.header(QNetworkRequest.ContentLengthHeader)
        if content_length is not None:
            har["bodySize"] = content_length
    return har

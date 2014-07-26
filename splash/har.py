# -*- coding: utf-8 -*-
"""
Module with helper utilities to serialize QWebkit objects to HAR.
See http://www.softwareishard.com/blog/har-12-spec/.
"""
from __future__ import absolute_import

from PyQt4.QtCore import Qt
from PyQt4.QtNetwork import QNetworkRequest, QNetworkReply


def headers2har(request_or_reply):
    """ Return HAR-encoded request or reply headers """
    return [
        {
            "name": bytes(header_name).decode('latin1'),
            "value": bytes(request_or_reply.rawHeader(header_name)).decode('latin1'),
        }
        for header_name in request_or_reply.rawHeaderList()
    ]


def request_cookies2har(request):
    """ Return HAR-encoded cookies of QNetworkRequest """
    cookies = request.header(QNetworkRequest.CookieHeader)
    return cookies2har(cookies)


def reply_cookies2har(reply):
    """ Return HAR-encoded cookies of QNetworkReply """
    cookies = reply.header(QNetworkRequest.SetCookieHeader)
    return cookies2har(cookies)


def cookies2har(cookies):
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
        # "httpVersion": "HTTP/1.1",  # XXX: how to get HTTP version?
        "cookies": reply_cookies2har(reply),
        "headers": headers2har(reply),
        # "content": {},
        # "headersSize" : -1,
        # "bodySize" : -1,
    }

    status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
    if not status.isNull():
        status, ok = status.toInt()
        res["status"] = int(status)

    status_text = reply.attribute(QNetworkRequest.HttpReasonPhraseAttribute)
    if not status_text.isNull():
        res["statusText"] = bytes(status_text.toByteArray()).decode('latin1')

    redirect_url = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
    if not redirect_url.isNull():
        res["redirectURL"] = unicode(redirect_url.toString())

    return res

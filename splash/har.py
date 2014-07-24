# -*- coding: utf-8 -*-
"""
Module with helper utilities to serialize QWebkit objects to HAR.
See http://www.softwareishard.com/blog/har-12-spec/.
"""
from __future__ import absolute_import
from PyQt4.QtCore import QVariant
from PyQt4.QtNetwork import QNetworkRequest, QNetworkReply
from splash.qtutils import OPERATION_NAMES

def request2har(request, operation=None, outgoingData=None):
    """ Serialize QNetworkRequest to HAR. """
    res = {
        # "method": "GET",
        "url": unicode(request.url().toString()),
        # "httpVersion": "HTTP/1.1",
        # "cookies": [],
        # "headers": [],
        # "queryString" : [],
        # "postData" : {},
        # "headersSize" : -1,
        # "bodySize" : -1,
    }
    method = OPERATION_NAMES.get(operation, None)
    if method is not None:
        res['method'] = method

    if outgoingData is not None:
        res['bodySize'] = len(outgoingData)

    return res


def reply2har(reply):
    """ Serialize QNetworkReply to HAR. """
    res = {
        # "httpVersion": "HTTP/1.1",
        # "cookies": [],
        # "headers": [],
        # "content": {},
        #
        # "headersSize" : 160,
        # "bodySize" : 850,
        # "comment" : ""
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

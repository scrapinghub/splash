# -*- coding: utf-8 -*-
"""
Module with helper utilities to serialize QWebkit objects to HAR.
See http://www.softwareishard.com/blog/har-12-spec/.
"""
from __future__ import absolute_import
from datetime import datetime

from PyQt4.QtCore import Qt
from PyQt4.QtNetwork import QNetworkRequest, QNetworkReply


def format_datetime(dt):
    """ Format datetime.datetime object to make HAR validator happy """
    return dt.isoformat() + 'Z'


def get_duration(start, end=None):
    """ Return duration between `start` and `end` datetimes in HAR format """
    if end is None:
        end = datetime.utcnow()
    elapsed = (end-start).total_seconds()
    return elapsed * 1000  # ms


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
        res["statusText"] = "?"

    redirect_url = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
    if not redirect_url.isNull():
        res["redirectURL"] = unicode(redirect_url.toString())
    else:
        res["redirectURL"] = ""

    return res


SCHEMA = {
    "type": "object",
    "properties": {
        "log": {
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "creator": {"$ref": "#/defs/creatorType"},
                "browser": {"$ref": "#/defs/browserType"},
                "pages": {"type": "array", "items": {"$ref": "#/defs/pageType"}},
                "entries": {"type": "array", "items": {"$ref": "#/defs/entryType"}},
                "comment": {"type": "string"}
            },
            "required": ["version", "creator", "browser", "entries"],
        }
    },
    "required": ["log"],
    "defs": {
        "creatorType": {
            "id": "creatorType",
            "description": "Name and version info of the log creator app.",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string"},
                "comment": {"type": "string"},
            },
            "required": ["name", "version"]
        },
        "browserType": {
            "id": "browserType",
            "description": "Name and version info of used browser.",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string"},
                "comment": {"type": "string"},
            },
            "required": ["name", "version"]
        },
        "pageType": {
            "description": "Exported web page",
            "type": "object",
            "properties": {
                "startedDateTime": {"type": "string", "format": "date-time"},
                "id": {"type": "string", "unique": True},
                "title": {"type": "string"},
                "pageTimings": {"$ref": "#/defs/pageTimingsType"},
                "comment": {"type": "string"},
            },
            "required": ["startedDateTime", "id", "title", "pageTimings"]
        },
        "entryType": {
            "type": "object",
            "properties": {
                "pageref": {"type": "string"},
                "startedDateTime": {"type": "string", "format": "date-time"},
                "time": {"type": "number", "minimum": 0},
                "request" : {"$ref": "#/defs/requestType"},
                "response" : {"$ref": "#/defs/responseType"},
                "cache" : {"$ref": "#/defs/cacheType"},
                "timings" : {"$ref": "#/defs/timingsType"},
                "serverIPAddress" : {"type": "string"},
                "connection" : {"type": "string"},
                "comment": {"type": "string"},
            },
            "required": ["startedDateTime", "time", "request", "response", "cache", "timings"]
        },
        "pageTimingsType": {
            "type": "object",
            "properties": {
                "onContentLoad": {"type": "number", "minimum": -1},
                "onLoad": {"type": "number", "minimum": -1},
                "comment": {"type": "string"},
            },
        },
        "requestType": {
            "type": "object",
            "properties": {
                "method": {"type": "string"},
                "url": {"type": "string"},
                "httpVersion": {"type" : "string"},
                "cookies" : {"type": "array", "items": {"$ref": "#/defs/cookieType"}},
                "headers" : {"type": "array", "items": {"$ref": "#/defs/recordType"}},
                "queryString" : {"type": "array", "items": {"$ref": "#/defs/recordType"}},
                "postData" : {"$ref": "#/defs/postDataType"},
                "headersSize" : {"type": "integer"},
                "bodySize" : {"type": "integer"},
                "comment": {"type": "string"},
            },
            "required": ["method", "url", "httpVersion", "cookies", "headers", "queryString", "headersSize", "bodySize"]
        },
        "responseType": {
            "type": "object",
            "properties": {
                "status": {"type": "integer"},
                "statusText": {"type": "string"},
                "httpVersion": {"type": "string"},
                "cookies" : {"type": "array", "items": {"$ref": "#/defs/cookieType"}},
                "headers" : {"type": "array", "items": {"$ref": "#/defs/recordType"}},
                "content" : {"$ref": "#/defs/contentType"},
                "redirectURL" : {"type": "string"},
                "headersSize" : {"type": "integer"},
                "bodySize" : {"type": "integer"},
                "comment": {"type": "string"}
            },
            "required": ["status", "statusText", "httpVersion",
                         "cookies", "headers", "content", "redirectURL",
                         "headersSize", "bodySize"]
        },
        "cacheType": {
            "type": "object",
            "properties": {
                "beforeRequest": {"$ref": "#/defs/cacheEntryType"},
                "afterRequest": {"$ref": "#/defs/cacheEntryType"},
                "comment": {"type": "string"}
            }
        },
        "timingsType": {
            "type": "object",
            "properties": {
                "dns": {"type": "number", "minimum": -1},
                "connect": {"type": "number", "minimum": -1},
                "blocked": {"type": "number", "minimum": -1},
                "send": {"type": "number", "minimum": -1},
                "wait": {"type": "number", "minimum": -1},
                "receive": {"type": "number", "minimum": -1},
                "ssl": {"type": "number", "minimum": -1},
                "comment": {"type": "string"}
            },
            "required": ["send", "wait", "receive"]
        },
        "cookieType": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "string"},
                "path": {"type": "string"},
                "domain" : {"type": "string"},
                "expires" : {"type": "string"},
                "httpOnly" : {"type": "boolean"},
                "secure" : {"type": "boolean"},
                "comment": {"type": "string"},
            },
            "required": ["name", "value"]
        },
        "recordType": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "string"},
                "comment": {"type": "string"},
            },
            "required": ["name", "value"],
        },
        "postDataType": {
            "type": "object",
            "properties": {
                "mimeType": {"type": "string"},
                "text": {"type": "string"},
                "params": {
                    "type": "array",
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                        "fileName": {"type": "string"},
                        "contentType": {"type": "string"},
                        "comment": {"type": "string"},
                    },
                    "required": ["name"]
                },
                "comment": {"type": "string"}
            },
            "required": ["mimeType"]
        },
        "contentType": {
            "type": "object",
            "properties": {
                "size": {"type": "integer"},
                "compression": {"type": "integer"},
                "mimeType": {"type": "string"},
                "text": {"type": "string"},
                "encoding": {"type": "string"},
                "comment": {"type": "string"}
            },
            "required": ["size", "mimeType"]
        },
        "cacheEntryType": {
            "type": "object",
            "properties": {
                "expires": {"type": "string"},
                "lastAccess": {"type": "string"},
                "eTag": {"type": "string"},
                "hitCount": {"type": "integer"},
                "comment": {"type": "string"}
            },
            "required": ["lastAccess", "eTag", "hitCount"]
        }
    },
}


def validate(instance):
    """ Validate HAR data; raise an exception if it is invalid """
    import jsonschema
    format_checker = jsonschema.FormatChecker(['date-time'])
    return jsonschema.validate(instance, SCHEMA, format_checker=format_checker)

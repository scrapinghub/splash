# -*- coding: utf-8 -*-
"""
Module for validating HAR data. Uses official HAR JSON Schema.
"""
from __future__ import absolute_import


def validate(instance):
    """ Validate HAR data; raise an exception if it is invalid """
    validator = get_validator()
    validator.check_schema(SCHEMA)
    validator.validate(instance)


def get_validator():
    """ Return jsonschema validator to validate SCHEMA """
    import jsonschema
    format_checker = jsonschema.FormatChecker(['date-time'])
    return jsonschema.Draft4Validator(SCHEMA, format_checker=format_checker)


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

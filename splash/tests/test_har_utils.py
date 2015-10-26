# -*- coding: utf-8 -*-
import base64

import pytest

from splash.har.utils import get_response_body_bytes


def get_har_response(text, encoding):
    har_response = {
        "status": 200,
        "statusText": "OK",
        "httpVersion": "HTTP/1.1",
        "cookies": [],
        "headers": [],
        "content": {
            "size": len(text),
            "compression": 0,
            "mimeType": "text/html; charset=utf-8",
            "text": text,
        },
        "redirectURL": "",
        "headersSize" : -1,
        "bodySize" : -1,
    }
    if encoding is not None:
        har_response['content']['encoding'] = encoding
    return har_response


@pytest.mark.parametrize(["text", "encoding", "result"], [
    ["hello", None, b'hello'],
    [
        base64.b64encode(u"привет".encode('cp1251')).decode('ascii'),
        'base64',
        u"привет".encode('cp1251')
    ],
    ["", None, b""],
    ["", 'base64', b""],
    [u"привет", None, u"привет".encode('utf8')],
    [u"привет", 'binary', u"привет".encode('utf8')],
    [u"привет".encode('utf8'), 'binary', u"привет".encode('utf8')],
])
def test_get_body_bytes(text, encoding, result):
    har_response = get_har_response(text, encoding)
    assert get_response_body_bytes(har_response) == result


def test_body_bytes_bad_encoding():
    har_response = get_har_response("hello", "i-am-unknown")
    with pytest.raises(ValueError):
        get_response_body_bytes(har_response)

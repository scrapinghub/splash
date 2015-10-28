# -*- coding: utf-8 -*-
from __future__ import absolute_import
import base64
from operator import itemgetter
import itertools
from datetime import datetime


def format_datetime(dt):
    """ Format datetime.datetime object to make HAR validator happy """
    return dt.isoformat() + 'Z'


def get_duration(start, end=None):
    """ Return duration between `start` and `end` datetimes in HAR format """
    if end is None:
        end = datetime.utcnow()
    elapsed = (end - start).total_seconds()
    return int(elapsed * 1000)  # ms


def cleaned_har_entry(dct):
    return {k: v for (k, v) in dct.items() if k not in {'_tmp', '_idx'}}


def entries2pages(entries):
    """ Group HAR entries into pages by pageref """
    pages = []
    for pageref, group in itertools.groupby(entries, key=itemgetter("pageref")):
        pages.append(list(group))
    return pages


def get_response_body_bytes(har_response):
    """ Return binary response data """
    content = har_response['content']
    body = content.get('text', None)
    if body is None:
        return None
    encoding = content.get('encoding', None)
    if encoding == 'base64':
        return base64.b64decode(body)
    if encoding is None or encoding == 'binary':
        if not isinstance(body, bytes):
            return body.encode('utf8')
        return body
    else:
        raise ValueError("Unsupported HAR content encoding: %r" % encoding)

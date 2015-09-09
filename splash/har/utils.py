# -*- coding: utf-8 -*-
from __future__ import absolute_import
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

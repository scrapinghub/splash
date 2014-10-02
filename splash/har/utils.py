# -*- coding: utf-8 -*-
from __future__ import absolute_import
from datetime import datetime


def format_datetime(dt):
    """ Format datetime.datetime object to make HAR validator happy """
    return dt.isoformat() + 'Z'


def get_duration(start, end=None):
    """ Return duration between `start` and `end` datetimes in HAR format """
    if end is None:
        end = datetime.utcnow()
    elapsed = (end-start).total_seconds()
    return int(elapsed * 1000)  # ms


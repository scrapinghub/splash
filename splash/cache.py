# -*- coding: utf-8 -*-
from __future__ import absolute_import
from PyQt4.QtNetwork import QNetworkDiskCache
from splash import defaults


def construct(path=defaults.CACHE_PATH, size=defaults.CACHE_SIZE):
    cache = QNetworkDiskCache()
    cache.setCacheDirectory(path)
    cache.setMaximumCacheSize(size * 1024**2)
    return cache

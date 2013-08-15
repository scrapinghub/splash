# -*- coding: utf-8 -*-
from __future__ import absolute_import
from PyQt4.QtNetwork import QNetworkDiskCache
from splash import defaults

def construct(path=defaults.CACHE_PATH, size_kb=defaults.CACHE_MAXSIZE_KB):
    cache = QNetworkDiskCache()
    cache.setCacheDirectory(path)
    cache.setMaximumCacheSize(size_kb * 1024)
    return cache

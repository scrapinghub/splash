# -*- coding: utf-8 -*-
from __future__ import absolute_import
from PyQt4.QtNetwork import QNetworkDiskCache
from twisted.python import log
from splash import config


def construct(path=config.CACHE_PATH, size=config.CACHE_SIZE):
    log.msg("Initializing cache on %s (maxsize: %d Mb)" % (path, size))
    cache = QNetworkDiskCache()
    cache.setCacheDirectory(path)
    cache.setMaximumCacheSize(size * 1024**2)
    cache.cacheSize()  # forces immediate initialization
    return cache

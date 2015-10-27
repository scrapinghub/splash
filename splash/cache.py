# -*- coding: utf-8 -*-
from __future__ import absolute_import
from PyQt4.QtNetwork import QNetworkDiskCache
from twisted.python import log
from splash.config import settings


def construct(path=settings.CACHE_PATH, size=settings.CACHE_SIZE):
    log.msg("Initializing cache on %s (maxsize: %d Mb)" % (path, size))
    cache = QNetworkDiskCache()
    cache.setCacheDirectory(path)
    cache.setMaximumCacheSize(size * 1024**2)
    cache.cacheSize()  # forces immediate initialization
    return cache

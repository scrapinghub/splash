# -*- coding: utf-8 -*-
""" Splash periodic monitoring tasks """
from __future__ import absolute_import, division
import gc
import time

from splash.utils import memory_to_absolute, get_ru_maxrss, get_mem_usage, MB
from splash.qtutils import clear_caches


def monitor_maxrss(maxrss, check_intreval=60):
    from twisted.internet import reactor, task
    from twisted.python import log

    maxrss = memory_to_absolute(maxrss)

    def check_maxrss():
        if get_ru_maxrss() > maxrss * MB:
            log.msg("maxrss exceeded %d MB, shutting down..." % maxrss)
            reactor.stop()

    if maxrss:
        log.msg("maxrss limit: %d MB" % maxrss)
        t = task.LoopingCall(check_maxrss)
        t.start(check_intreval, now=False)


def monitor_currss(threshold, verbosity, min_interval=30, check_interval=10):
    """
    Monitor current memory usage and try to free memory
    if it exceeds a `threshold` (in MB) and at least `min_interval`
    seconds passed since last cleanup.

    Memory is measured on event loop ticks. Temporary memory usage
    spikes may not be taken in account.
    """
    from twisted.internet import task
    from twisted.python import log

    objgraph = None
    if verbosity >= 3:
        try:
            import objgraph
            objgraph.show_growth()
        except ImportError:
            pass

    threshold = memory_to_absolute(threshold)
    last_cleanup = [-1.0]

    def check_memusage():
        rss = get_mem_usage()
        peak = get_ru_maxrss()

        if verbosity >= 2:
            log.msg("Memory usage: %0.1fMB (%0.1fMB peak)" % (rss / MB,
                                                              peak / MB))

        if rss > threshold * MB:
            now = time.time()
            interval = now - last_cleanup[0]
            if interval > min_interval:
                if verbosity >= 1:
                    log.msg(
                        "Splash uses too much memory: %0.1f > %0.1f. "
                        "Cleaning up WebKit caches.." % (rss / MB, threshold)
                    )

                clear_caches()
                gc.collect()

                rss_new = get_mem_usage()
                if verbosity >= 1:
                    log.msg("Memory freed: %0.1f MB" % ((rss - rss_new) / MB))
                last_cleanup[0] = time.time()

                if verbosity >= 3 and objgraph:
                    objgraph.show_growth(limit=100)
            else:
                if verbosity >= 2:
                    log.msg(
                        "Splash uses too much memory (%0.1f > %0.1f.), but "
                        "the cache was cleared recently (%0.1f seconds ago)" %
                        (rss / MB, threshold, interval)
                    )

    if threshold:
        log.msg("cleanup threshold: %d MB" % threshold)
        t = task.LoopingCall(check_memusage)
        t.start(check_interval, now=False)

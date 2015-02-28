#!/usr/bin/env python

"""
Splash benchmark script.

It takes a directory downloaded with splash & httrack, fires up a static file
server and runs a series of requests via splash on those downloaded pages.

"""

import logging
import os
import random
import shutil
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from glob import glob
from multiprocessing.pool import ThreadPool
from pprint import pformat
from time import time

import requests
from splash.benchmark.file_server import serve_files
from splash.tests.utils import SplashServer

#: Port at which static pages will be served.
PORT = 8806
#: Static pages to be used in the benchmark.
PAGES = glob('localhost_8806/*.html')
#: Combinations of width & height to test.
WIDTH_HEIGHT = [(None, None), (500, None), (None, 500), (500, 500)]
# XXX: add benchmark of different API endpoints.
SPLASH_LOG = 'splash.log'
#: This script is used to collect maxrss & cpu time from splash process.
GET_PERF_STATS_SCRIPT = """
function main(splash)
  return splash:get_perf_stats()
end
"""

parser = ArgumentParser(description=__doc__,
                        formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument('--seed', type=int, default=1234, help='PRNG seed number')
parser.add_argument('--thread-count', type=int, default=1,
                    help='Request thread count')
parser.add_argument('--request-count', type=int, default=10,
                    help='Benchmark request count')


def generate_requests(splash, args):
    log = logging.getLogger('generate_requests')
    log.info("Using pRNG seed: %s", args.seed)
    rng = random.Random(args.seed)
    for i in xrange(args.request_count):
        page = rng.choice(PAGES)
        width, height = rng.choice(WIDTH_HEIGHT)
        url = 'http://localhost:%d/%s' % (PORT, page)
        yield (i + 1, args.request_count,
               {'url': splash.url('render.png'),
                'params': {'url': url, 'width': width, 'height': height}})


def parallel_map(func, iterable, thread_count):
    if thread_count == 1:
        return map(func, iterable)
    else:
        pool = ThreadPool(thread_count)
        return pool.map(func, iterable)


def invoke_request(invoke_args):
    log = logging.getLogger('bench_worker')
    req_no, total_reqs, kwargs = invoke_args
    log.info("Initiating request %d/%d: %s", req_no, total_reqs, kwargs)
    stime = time()
    requests.get(**kwargs)
    etime = time()
    return {'start_time': stime,
            'end_time': etime,
            'duration': etime - stime,
            'endpoint': kwargs['url'],
            'site': kwargs['params']['url'],
            'width': kwargs['params']['width'],
            'height': kwargs['params']['height']}


def main():
    log = logging.getLogger("benchmark")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)

    splash = SplashServer(
        logfile=SPLASH_LOG,
        extra_args=['--disable-lua-sandbox',
                    '--disable-xvfb',
                    '--max-timeout=600'])

    with splash, serve_files(PORT):
        start_time = time()
        results = parallel_map(invoke_request, generate_requests(splash, args),
                               args.thread_count)
        end_time = time()
        resources = requests.get(
            splash.url('execute'),
            params={'lua_source': GET_PERF_STATS_SCRIPT}).json()

    log.info("Request stats:\n%s", pformat(dict(enumerate(results))))
    log.info("Splash max RSS: %s B", resources['maxrss'])
    log.info("Splash CPU time elapsed: %.2f sec", resources['cputime'])
    log.info("Wallclock time elapsed: %.2f sec", end_time - start_time)


if __name__ == '__main__':
    main()

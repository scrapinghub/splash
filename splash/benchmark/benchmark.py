#!/usr/bin/env python

"""
Splash benchmark script.

It takes a directory downloaded with splash & httrack, fires up a static file
server and runs a series of requests via splash on those downloaded pages.

"""

import logging
import random
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from glob import glob
from multiprocessing.pool import ThreadPool

import requests
from splash.file_server import serve_files
from splash.tests.utils import SplashServer

PORT = 8806
#: URLs to benchmark against.
PAGES = glob('localhost_8806/*.html')
#: Combinations of width & height to test.
WIDTH_HEIGHT = [(None, None), (500, None), (None, 500), (500, 500)]
# XXX: add benchmark of different API endpoints.
SPLASH_LOG = 'splash.log'

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
    return requests.get(**kwargs)


def main():
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)

    with SplashServer(logfile=SPLASH_LOG,
                      extra_args=['--disable-lua-sandbox',
                                  '--disable-xvfb',
                                  '--max-timeout=600']) as splash, \
         serve_files(PORT):
        parallel_map(invoke_request, generate_requests(splash, args),
                     args.thread_count)


if __name__ == '__main__':
    main()

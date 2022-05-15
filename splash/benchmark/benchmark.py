#!/usr/bin/env python

"""
Splash benchmark script.

It takes a directory downloaded with splash & httrack, fires up a static file
server and runs a series of requests via splash on those downloaded pages.

"""

import json
import logging
import os
import random
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, FileType
from glob import glob
from multiprocessing.pool import ThreadPool
from pprint import pformat
from time import time
import re
import sys

import requests


def make_render_png_req(splash, params):
    """Make PNG render request via render.png endpoint."""
    return {'url': splash.url('render.png'),
            'params': params}


def make_render_json_req(splash, params):
    """Make PNG render request via JSON endpoint."""
    json_params = params.copy()
    json_params['png'] = 1
    return {'url': splash.url('render.json'),
            'params': json_params}


def make_render_png_lua_req(splash, params):
    """Make PNG render request via Lua execute endpoint."""
    lua_params = params.copy()
    lua_params['lua_source'] = """
function main(splash)
  assert(splash:go(splash.args.url))
  if splash.args.wait then
    assert(splash:wait(splash.args.wait))
  end
  splash:set_result_content_type("image/png")
  return splash:png{width=splash.args.width,
                    height=splash.args.height,
                    render_all=splash.args.render_all}
end
"""
    return {'url': splash.url('execute'),
            'params': lua_params}


def make_render_html_req(splash, params):
    """Make HTML render request via render.html endpoint."""
    return {'url': splash.url('render.html'),
            'params': params}


def make_render_html_json_req(splash, params):
    """Make HTML render request via JSON endpoint."""
    json_params = params.copy()
    json_params['html'] = 1
    return {'url': splash.url('render.json'),
            'params': json_params}


def make_render_html_lua_req(splash, params):
    """Make HTML render request via Lua execute endpoint."""
    lua_params = params.copy()
    lua_params['lua_source'] = """
function main(splash)
  assert(splash:go(splash.args.url))
  if splash.args.wait then
    assert(splash:wait(splash.args.wait))
  end
  splash:set_result_content_type("text/html; charset=UTF-8")
  return splash:html{}
end
"""
    return {'url': splash.url('execute'),
            'params': lua_params}


#: Same resource may be rendered by various endpoints with slightly varying
#: parameter combinations.  Request factories set those combinations up.
REQ_FACTORIES = {
    'png': [
        make_render_png_req,
        make_render_json_req,
        make_render_png_lua_req,
    ],
    'html': [
        make_render_html_req,
        make_render_html_json_req,
        make_render_html_lua_req,
    ],
}


#: Port at which static pages will be served.
PORT = 8806
#: Combinations of width & height to test.
WIDTH_HEIGHT = [(None, None), (500, None), (None, 500), (500, 500)]
#: Splash & fileserver log filenames (set to None to put it to stderr).
SPLASH_LOG = 'splash.log'
FILESERVER_LOG = 'fileserver.log'
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
parser.add_argument('--sites-dir', type=str, default='sites', required=True,
                    help='Directory with downloaded sites')
parser.add_argument('--file-server', metavar='HOST:PORT',
                    help='Use existing file server instance available at HOST:PORT')
parser.add_argument('--splash-server', metavar='HOST:PORT',
                    help='Use existing Splash instance available at HOST:PORT')
parser.add_argument('--out-file', type=FileType(mode='w'), default=sys.stdout,
                    help='Write detailed request information in this file')
parser.add_argument('--render-type', choices=('html', 'png'), default='png',
                    help=('Type of rendering to benchmark'
                          ' (either "html" or "png")'))


def generate_requests(splash, file_server, args):
    log = logging.getLogger('generate_requests')
    log.info("Using pRNG seed: %s", args.seed)

    # Static pages (relative to sites_dir) to be used in the benchmark.
    log.info("sites dir: %s", args.sites_dir)
    sites_found = glob(os.path.join(args.sites_dir, 'localhost_8806', '*.html'))
    log.info("sites found: %s", sites_found)
    pages = [re.sub('^%s/' % args.sites_dir.rstrip('/'), '', v) for v in sites_found]
    for p in pages:
        log.info("Using page for benchmark: %s", p)

    request_factories = REQ_FACTORIES[args.render_type]

    rng = random.Random(args.seed)
    for i in xrange(args.request_count):
        page = rng.choice(pages)
        width, height = rng.choice(WIDTH_HEIGHT)
        req_factory = rng.choice(request_factories)
        url = file_server.url(page)
        params = {'url': url, 'render_all': 1, 'wait': 0.1,
                  'width': width, 'height': height}
        log.debug("Req factory: %s, params: %s", req_factory, params)
        yield (i + 1, args.request_count, req_factory(splash, params))


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
    response = requests.get(**kwargs)
    etime = time()
    if response.status_code != 200:
        log.error("Non-OK response:\n%s", response.text)
    return {'start_time': stime,
            'end_time': etime,
            'duration': etime - stime,
            'endpoint': kwargs['url'],
            'status': response.status_code,
            'site': kwargs['params']['url'],
            'width': kwargs['params']['width'],
            'height': kwargs['params']['height']}


class ExistingServerWrapper(object):
    """Wrapper for pre-existing Splash instance."""
    def __init__(self, server):
        self.server = server
        if not self.server.startswith('http://'):
            self.server = 'http://' + self.server

    def url(self, endpoint):
        return self.server + '/' + endpoint

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def main():
    log = logging.getLogger("benchmark")
    args = parser.parse_args()
    (logging.getLogger('requests.packages.urllib3.connectionpool')
     .setLevel(logging.WARNING))
    logging.basicConfig(level=logging.DEBUG)

    if args.splash_server:
        splash = ExistingServerWrapper(args.splash_server)
    else:
        from splash.tests.utils import SplashServer
        splash = SplashServer(
            logfile=SPLASH_LOG,
            extra_args=['--disable-lua-sandbox',
                        '--disable-xvfb',
                        '--max-timeout=600'])

    if args.file_server:
        file_server = ExistingServerWrapper(args.file_server)
    else:
        from splash.benchmark.file_server import FileServerSubprocess
        file_server = FileServerSubprocess(port=PORT,
                                           path=args.sites_dir,
                                           logfile=FILESERVER_LOG)

    with splash, file_server:
        log.info("Servers are up, starting benchmark...")
        start_res = requests.get(
            splash.url('execute'),
            params={'lua_source': GET_PERF_STATS_SCRIPT}).json()
        start_time = time()
        results = parallel_map(invoke_request,
                               generate_requests(splash, file_server, args),
                               args.thread_count)
        end_time = time()
        end_res = requests.get(
            splash.url('execute'),
            params={'lua_source': GET_PERF_STATS_SCRIPT}).json()

    log.info("Writing stats to %s", args.out_file.name)
    args.out_file.write(json.dumps(
        {'maxrss': end_res['maxrss'],
         'cputime': end_res['cputime'] - start_res['cputime'],
         'walltime': end_time - start_time,
         'requests': results},
        indent=2))
    log.info("Splash max RSS: %s B", end_res['maxrss'])
    log.info("Splash CPU time elapsed: %.2f sec",
             end_res['cputime'] - start_res['cputime'])
    log.info("Wallclock time elapsed: %.2f sec", end_time - start_time)


if __name__ == '__main__':
    main()

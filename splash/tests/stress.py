import sys, requests, random, optparse, time, json
from itertools import islice
from Queue import Queue
from threading import Thread
from collections import Counter
import requests

from .utils import SplashServer, MockServer

class StressTest():

    def __init__(self, reqs, host="localhost:8050", requests=1000, concurrency=50, shuffle=False, verbose=False):
        self.reqs = reqs
        self.host = host
        self.requests = requests
        self.concurrency = concurrency
        self.shuffle = shuffle
        self.verbose = verbose

    def run(self):
        args = list(islice(self.reqs, self.requests))
        if self.shuffle:
            random.shuffle(args)
        print "Total requests: %d" % len(args)
        print "Concurrency   : %d" % self.concurrency

        starttime = time.time()
        q, p = Queue(), Queue()
        for _ in xrange(self.concurrency):
            t = Thread(target=worker, args=(self.host, q, p, self.verbose))
            t.daemon = True
            t.start()
        for a in args:
            q.put(a)
        q.join()

        outputs = []
        for _ in xrange(self.requests):
            outputs.append(p.get())

        elapsed = time.time() - starttime
        print
        print "Total requests: %d" % len(args)
        print "Concurrency   : %d" % self.concurrency
        print "Elapsed time  : %.3fs" % elapsed
        print "Avg time p/req: %.3fs" % (elapsed/len(args))
        print "Received (per status code or error):"
        for c, n in Counter(outputs).items():
            print "  %s: %d" % (c, n)


def worker(host, q, p, verbose=False):
    url = "http://%s/render.html" % host
    while True:
        try:
            args = q.get()
            t = time.time()
            r = requests.get(url, params=args)
            t = time.time() - t
            p.put(r.status_code)
            if verbose:
                print(". %d %.3fs %s" % (r.status_code, t, args))
            else:
                sys.stdout.write(".")
                sys.stdout.flush()
        except Exception as e:
            p.put(type(e))
            if verbose:
                print "E %.3fs %s" % (t, args)
            else:
                sys.stdout.write("E")
                sys.stdout.flush()
        finally:
            q.task_done()


class MockArgs(object):

    ok_urls = 0.5
    error_urls = 0.3
    timeout_urls = 0.2

    def __init__(self, requests=1000):
        self.requests = requests

    def _ok_urls(self):
        url = ["http://localhost:8998/jsrender"]
        return int(self.requests * self.ok_urls) * url

    def _error_urls(self):
        url = ["http://non-existent-host/"]
        return int(self.requests * self.error_urls) * url

    def _timeout_urls(self):
        url = ["http://localhost:8998/delay?n=10&timeout=0.5"]
        return int(self.requests * self.timeout_urls) * url

    def __iter__(self):
        ok_urls = self._ok_urls()
        error_urls = self._error_urls()
        timeout_urls = self._timeout_urls()
        print("Expected codes: HTTP200x%d, HTTP502x%d, HTTP504x%d" % (
            len(ok_urls), len(error_urls), len(timeout_urls)))
        urls = ok_urls + error_urls + timeout_urls
        return ({"url": x} for x in urls)


class ArgsFromUrlFile(object):

    def __init__(self, urlfile):
        self.urlfile = urlfile

    def __iter__(self):
        for line in open(self.urlfile):
            url = line.rstrip()
            if '://' not in url:
                url = 'http://' + url
            yield {"url": url, "timeout": 60}


class ArgsFromLogfile(object):

    def __init__(self, logfile):
        self.logfile = logfile

    def __iter__(self):
        for l in open(self.logfile):
            if "[stats]" in l:
                d = json.loads(l[33:].rstrip())
                yield d['args']


def lua_runonce(script, timeout=60., splash_args=None, **kwargs):
    """ Start splash server, execute lua script in it and return the output.

    :type script: str
    :param script: Script to be executed.
    :type timeout: float
    :param timeout: Timeout value for the execution request.
    :param splash_args: Extra parameters for splash server invocation.
    :type kwargs: dict
    :param kwargs: Any other parameters are passed as arguments to the request
                   and will be available via ``splash.args``.

    This function also starts a `MockServer`.  If `url` kwarg has scheme=mock,
    e.g., "mock://jsrender", it will be resolved as a url pointing to
    corresponding mock server resource.

    """
    if splash_args is None:
        splash_args = ['--disable-lua-sandbox',
                       '--allowed-schemes=file,http,https', ]
    with SplashServer(extra_args=splash_args) as s, \
         MockServer() as ms:
        if kwargs.get('url', '').startswith('mock://'):
            kwargs['url'] = ms.url(kwargs['url'][7:])
        params = {'lua_source': script}
        params.update(kwargs)
        resp = requests.get(s.url('execute'), params=params, timeout=timeout)
        if resp.ok:
            return resp.content
        else:
            raise RuntimeError(resp.text)


def benchmark_png(url, viewport=None, wait=0.5, render_all=1,
                  width=None, height=None, nrepeats=3, timeout=60.):
    f = """
function main(splash)
    local resp, err = splash:go(splash.args.url)
    assert(resp, err)
    assert(splash:wait(tonumber(splash.args.wait)))

    -- if viewport is 'full' it should be set only after waiting
    if splash.args.viewport ~= nil and splash.args.viewport ~= "full" then
      local w, h = string.match(splash.args.viewport, '^(%d+)x(%d+)')
      if w == nil or h == nil then
        error('Invalid viewport size format: ' .. splash.args.viewport)
      end
      splash:set_viewport_size(tonumber(w), tonumber(h))
    end

    local susage = splash:get_perf_stats()
    local nrepeats = tonumber(splash.args.nrepeats)
    local render_all = splash.args.render_all or splash.args.viewport == 'full'
    local png, err
    for i = 1, nrepeats do
        png, err = splash:png{width=splash.args.width,
                              height=splash.args.height,
                              render_all=render_all}
        assert(png, err)
    end
    local eusage = splash:get_perf_stats()
    return {
        wallclock_secs=(eusage.walltime - susage.walltime) / nrepeats,
        maxrss=eusage.maxrss,
        cpu_secs=(eusage.cputime - susage.cputime) / nrepeats,
        png=png,
    }
end
    """
    return json.loads(lua_runonce(
        f, url=url, width=width, height=height, render_all=render_all,
        nrepeats=nrepeats, wait=wait, viewport=viewport, timeout=timeout))


def parse_opts():
    op = optparse.OptionParser()
    op.add_option("-H", dest="host", default="localhost:8050",
            help="splash hostname & port (default: %default)")
    op.add_option("-u", dest="urlfile", metavar="FILE",
            help="read urls from FILE instead of using mock server ones")
    op.add_option("-l", dest="logfile", metavar="FILE",
            help="read urls from splash log file (useful for replaying)")
    op.add_option("-s", dest="shuffle", action="store_true", default=False,
            help="shuffle (randomize) requests (default: %default)")
    op.add_option("-v", dest="verbose", action="store_true", default=False,
            help="verbose mode (default: %default)")
    op.add_option("-c", dest="concurrency", type="int", default=50,
            help="concurrency (default: %default)")
    op.add_option("-n", dest="requests", type="int", default=1000,
            help="number of requests (default: %default)")
    return op.parse_args()


def main():
    opts, _ = parse_opts()
    if opts.urlfile:
        urls = ArgsFromUrlFile(opts.urlfile)
    elif opts.logfile:
        urls = ArgsFromLogfile(opts.logfile)
    else:
        urls = MockArgs(opts.requests)
    t = StressTest(urls, opts.host, opts.requests, opts.concurrency, opts.shuffle, opts.verbose)
    t.run()

if __name__ == "__main__":
    main()

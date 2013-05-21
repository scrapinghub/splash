import sys, requests, random, optparse, time
from Queue import Queue
from threading import Thread
from collections import Counter
from tempfile import NamedTemporaryFile
from splash2.tests.utils import TestServers


class StressTest():

    ok_urls = 0.5
    error_urls = 0.3
    timeout_urls = 0.2

    def __init__(self, total=1000, concurrency=50):
        self.requests = total
        self.concurrency = concurrency
        

    def _ok_urls(self):
        url = ["http://localhost:8050/render.html?url=http://localhost:8998/jsrender"]
        return int(self.requests * self.ok_urls) * url

    def _error_urls(self):
        url = ["http://localhost:8050/render.html?url=http://non-existent-host/"]
        return int(self.requests * self.error_urls) * url

    def _timeout_urls(self):
        url = ["http://localhost:8050/render.html?url=http://localhost:8998/delay?n=10&timeout=0.5"]
        return int(self.requests * self.timeout_urls) * url

    def run(self):
        f = NamedTemporaryFile(prefix="splash-stress-", suffix=".log", delete=False)
        # we need to use log file to prevent deadlocks on heavy loads
        with TestServers(logfile=f.name):
            ok_urls = self._ok_urls()
            error_urls = self._error_urls()
            timeout_urls = self._timeout_urls()
            urls = ok_urls + error_urls + timeout_urls
            random.shuffle(urls)

            print "Total requests: %d" % len(urls)
            print "Concurrency   : %d" % self.concurrency
            print "Log file      : %s" % f.name

            starttime = time.time()
            q, p = Queue(), Queue()
            for _ in xrange(self.concurrency):
                t = Thread(target=worker, args=(q, p))
                t.daemon = True
                t.start()
            for url in urls:
                q.put(url)
            q.join()

            outputs = []
            for _ in xrange(self.requests):
                outputs.append(p.get())

            elapsed = time.time() - starttime
            expected = {
                200: len(ok_urls),
                502: len(error_urls),
                504: len(timeout_urls),
            }
            print
            print "Total requests: %d" % len(urls)
            print "Concurrency   : %d" % self.concurrency
            print "Log file      : %s" % f.name
            print "Elapsed time  : %.3fs" % elapsed
            print "Avg time p/req: %.3fs" % (elapsed/len(urls))
            print "Received/Expected (per status code or error):"
            for c, n in Counter(outputs).items():
                print "  %s: %d/%d" % (c, n, expected.get(c, 0))

def worker(q, p):
    while True:
        try:
            url = q.get()
            r = requests.get(url)
            p.put(r.status_code)
            sys.stdout.write(".")
            sys.stdout.flush()
        except Exception as e:
            p.put(type(e))
            sys.stdout.write("E")
            sys.stdout.flush()
        finally:
            q.task_done()

def parse_opts():
    op = optparse.OptionParser()
    op.add_option("-c", dest="concurrency", type="int", default=50,
            help="concurrency (default: %default)")
    op.add_option("-n", dest="requests", type="int", default=1000,
            help="number of requests (default: %default)")
    return op.parse_args()

def main():
    opts, _ = parse_opts()
    t = StressTest(opts.requests, opts.concurrency)
    t.run()

if __name__ == "__main__":
    main()

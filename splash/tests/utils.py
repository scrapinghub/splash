import sys, os, time
from subprocess import Popen, PIPE

def get_testenv():
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd()
    return env

class SplashServer():

    def __init__(self, logfile=None):
        self.logfile = logfile

    def __enter__(self):
        args = [sys.executable, '-u', '-m', 'splash.server']
        if self.logfile:
            args += ['-f', self.logfile]
        self.proc = Popen(args, stderr=PIPE, env=get_testenv())
        self.proc.poll()
        if self.proc.returncode:
            msg = "unable to start splash server. error code: %d - stderr follows: \n%s" % \
                (self.proc.returncode, self.proc.stderr.read())
            raise RuntimeError(msg)

        # wait until server starts writing debug messages,
        # then wait a bit more to make it more likely to be online
        self.proc.stderr.readline()
        time.sleep(0.2)

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.wait()
        time.sleep(0.2)


class MockServer():

    def __enter__(self):
        self.proc = Popen([sys.executable, '-u', '-m', 'splash.tests.mockserver'],
            stdout=PIPE, env=get_testenv())
        self.proc.stdout.readline()
        time.sleep(0.1)

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.wait()
        time.sleep(0.2)


class TestServers():

    def __init__(self, logfile=None):
        self.logfile = logfile

    def __enter__(self):
        self.mockserver = MockServer()
        self.mockserver.__enter__()
        self.splashserver = SplashServer(self.logfile)
        self.splashserver.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self.splashserver.__exit__(None, None, None)
        self.mockserver.__exit__(None, None, None)

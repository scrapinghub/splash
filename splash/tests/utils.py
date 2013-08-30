import sys, os, time, tempfile, shutil, socket, fcntl
from subprocess import Popen, PIPE
from splash import defaults

def get_testenv():
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd()
    return env


def _ephemeral_port():
    s = socket.socket()
    s.bind(("", 0))
    return s.getsockname()[1]

def _non_block_read(output):
    fd = output.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        return output.read()
    except Exception:
        return ""


class SplashServer():

    def __init__(self, logfile=None, proxy_profiles_path=None, portnum=None):
        self.logfile = logfile
        self.proxy_profiles_path = proxy_profiles_path
        self.portnum = str(portnum) if portnum is not None else str(_ephemeral_port())
        self.tempdir = tempfile.mkdtemp()

    def __enter__(self):
        args = [sys.executable, '-u', '-m', 'splash.server']
        args += ['--cache-path', self.tempdir]
        args += ['--port', self.portnum]
        if self.logfile:
            args += ['-f', self.logfile]
        if self.proxy_profiles_path:
            args += ['--proxy-profiles-path', self.proxy_profiles_path]

        self.proc = Popen(args, stderr=PIPE, env=get_testenv())
        self.proc.poll()
        if self.proc.returncode:
            msg = "unable to start splash server. error code: %d - stderr follows: \n%s" % \
                (self.proc.returncode, self.proc.stderr.read())
            raise RuntimeError(msg)

        # wait until server starts writing debug messages,
        # then wait a bit more to make it more likely to be online, otherwise
        # it will fail on Mac OS X 10.8
        print(self.proc.stderr.readline())
        time.sleep(0.2)
        print(_non_block_read(self.proc.stderr))

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.wait()
        time.sleep(0.2)
        shutil.rmtree(self.tempdir)


class MockServer():

    def __enter__(self):
        self.proc = Popen([sys.executable, '-u', '-m', 'splash.tests.mockserver'],
            stdout=PIPE, env=get_testenv())
        print(self.proc.stdout.readline())
        time.sleep(0.1)
        print(_non_block_read(self.proc.stdout))

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.wait()
        time.sleep(0.2)


class TestServers():

    def __init__(self, logfile=None):
        self.logfile = logfile
        self.proxy_profiles_path = os.path.join(
            os.path.dirname(__file__),
            'proxy_profiles'
        )

    def __enter__(self):
        self.mockserver = MockServer()
        self.mockserver.__enter__()
        self.splashserver = SplashServer(self.logfile, self.proxy_profiles_path)
        self.splashserver.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self.splashserver.__exit__(None, None, None)
        self.mockserver.__exit__(None, None, None)

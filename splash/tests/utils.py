import sys, os, time, tempfile, shutil, socket, fcntl
from subprocess import Popen, PIPE


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

def _wait_for_port(portnum, delay=0.1, attempts=30):
    while attempts > 0:
        s = socket.socket()
        if s.connect_ex(('127.0.0.1', portnum)) == 0:
            s.close()
            return
        time.sleep(delay)
        attempts -= 1
    raise RuntimeError("Port %d is not open" % portnum)


class SplashServer(object):

    def __init__(self, logfile=None, proxy_profiles_path=None,
                 js_profiles_path=None, filters_path=None, portnum=None,
                 proxy_portnum=None, verbosity=3):
        self.logfile = logfile
        self.proxy_profiles_path = proxy_profiles_path
        self.js_profiles_path = js_profiles_path
        self.filters_path = filters_path
        self.portnum = portnum if portnum is not None else _ephemeral_port()
        self.proxy_portnum = proxy_portnum if proxy_portnum is not None else _ephemeral_port()
        self.verbosity = verbosity
        self.tempdir = tempfile.mkdtemp()

    def __enter__(self):
        args = [sys.executable, '-u', '-m', 'splash.server']
        args += ['--cache-path', self.tempdir]
        args += ['--port', str(self.portnum)]
        args += ['--verbosity', str(self.verbosity)]
        if self.logfile:
            args += ['-f', self.logfile]
        if self.proxy_profiles_path:
            args += ['--proxy-profiles-path', self.proxy_profiles_path]
        if self.js_profiles_path:
            args += ['--js-profiles-path', self.js_profiles_path]
        if self.filters_path:
            args += ['--filters-path', self.filters_path]
        if self.proxy_portnum:
            args += ['--proxy-portnum', str(self.proxy_portnum)]

        self.proc = Popen(args, stderr=PIPE, env=get_testenv())
        self.proc.poll()
        if self.proc.returncode:
            msg = "unable to start splash server. error code: %d - stderr follows: \n%s" % \
                (self.proc.returncode, self.proc.stderr.read())
            raise RuntimeError(msg)

        try:
            _wait_for_port(self.portnum)
        finally:
            print(_non_block_read(self.proc.stderr))

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.wait()
        time.sleep(0.2)
        shutil.rmtree(self.tempdir)


class MockServer(object):

    def __enter__(self):
        self.proc = Popen([sys.executable, '-u', '-m', 'splash.tests.mockserver'],
            stdout=PIPE, env=get_testenv())
        for port in (8998, 8999, 8990):
            _wait_for_port(port)
        print(_non_block_read(self.proc.stdout))

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.wait()
        time.sleep(0.2)


class TestServers(object):

    def __init__(self, logfile=None):
        self.logfile = logfile
        self.proxy_profiles_path = _path('proxy_profiles')
        self.js_profiles_path = _path('js_profiles')
        self.filters_path = _path('filters')

    def __enter__(self):
        self.mockserver = MockServer()
        self.mockserver.__enter__()
        self.splashserver = SplashServer(
            logfile=self.logfile,
            proxy_profiles_path=self.proxy_profiles_path,
            js_profiles_path=self.js_profiles_path,
            filters_path=self.filters_path,
        )
        self.splashserver.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self.splashserver.__exit__(None, None, None)
        self.mockserver.__exit__(None, None, None)

    def print_output(self):
        print(_non_block_read(self.splashserver.proc.stderr))
        print(_non_block_read(self.mockserver.proc.stdout))


def _path(*args):
    return os.path.join(os.path.dirname(__file__), *args)

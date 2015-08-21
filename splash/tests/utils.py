import sys, os, time, tempfile, shutil, socket, fcntl, signal
from subprocess import Popen, PIPE


try:
    socket.getaddrinfo('non-existing-host', 80)
    NON_EXISTING_RESOLVABLE = True
except socket.gaierror:
    NON_EXISTING_RESOLVABLE = False


def get_testenv():
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd()
    return env


def get_ephemeral_port():
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


def _wait_for_port(portnum, delay=0.1, attempts=100):
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
                 proxy_portnum=None, extra_args=None, verbosity=3):
        self.logfile = logfile
        self.proxy_profiles_path = proxy_profiles_path
        self.js_profiles_path = js_profiles_path
        self.filters_path = filters_path
        self.verbosity = verbosity
        self.portnum = portnum if portnum is not None else get_ephemeral_port()
        self.proxy_portnum = proxy_portnum if proxy_portnum is not None else get_ephemeral_port()
        self.tempdir = tempfile.mkdtemp()
        self.extra_args = extra_args or []

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

        args.extend(self.extra_args)

        self.proc = Popen(args, env=get_testenv())
        self.proc.poll()
        if self.proc.returncode is not None:
            msg = ("unable to start splash server. return code: %d" %
                   self.proc.returncode)
            raise RuntimeError(msg)
        _wait_for_port(self.portnum)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.proc is not None:
            self.proc.send_signal(signal.SIGINT)
            self.proc.wait()
            self.proc = None
            shutil.rmtree(self.tempdir)

    def url(self, path):
        return "http://localhost:%s/%s" % (self.portnum, path.lstrip('/'))

    def proxy_url(self):
        return "http://localhost:%s" % self.proxy_portnum


class MockServer(object):

    def __init__(self, http_port=None, https_port=None, proxy_port=None):
        self.http_port = http_port if http_port is not None else get_ephemeral_port()
        self.https_port = https_port if https_port is not None else get_ephemeral_port()
        self.proxy_port = proxy_port if proxy_port is not None else get_ephemeral_port()

    def __enter__(self):
        self.proc = Popen([
                sys.executable,
                '-u', '-m', 'splash.tests.mockserver',
                '--http-port', str(self.http_port),
                '--https-port', str(self.https_port),
                '--proxy-port', str(self.proxy_port),
            ],
            env=get_testenv()
        )
        for port in (self.http_port, self.https_port, self.proxy_port):
            _wait_for_port(port)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.wait()

    def url(self, path, gzip=True, host='localhost'):
        gzip_path = '' if not gzip else '/gzip'
        return "http://%s:%s%s/%s" % (
            host, self.http_port, gzip_path, path.lstrip('/')
        )

    def https_url(self, path):
        return "https://localhost:%s/%s" % (self.https_port, path.lstrip('/'))


class TestServers(object):

    def __init__(self, logfile=None):
        self.logfile = logfile
        self.tmp_folder = tempfile.mkdtemp("splash-tests-tmp")
        self.proxy_profiles_path = self._copy_test_folder('proxy_profiles')
        self.js_profiles_path = self._copy_test_folder('js_profiles')
        self.filters_path = self._copy_test_folder('filters')

        self.lua_modules = self._copy_test_folder('lua_modules')
        self.lua_sandbox_allowed_modules = ['emulation', 'utils', 'utils_patch', 'non_existing']

        self.mock_http_port = get_ephemeral_port()
        self.mock_https_port = get_ephemeral_port()
        self.mock_proxy_port = get_ephemeral_port()

        print("TestServers mock ports: %s http, %s https, %s proxy" % (
            self.mock_http_port, self.mock_https_port, self.mock_proxy_port))

        self._fix_testproxy_port()

    def _copy_test_folder(self, src, dst=None):
        src_path = test_path(src)
        dst_path = os.path.join(self.tmp_folder, dst or src)
        shutil.copytree(src_path, dst_path)
        return dst_path

    def _fix_testproxy_port(self):
        filename = os.path.join(self.proxy_profiles_path, 'test.ini')
        with open(filename, 'rb') as f:
            data = f.read()
        data = data.replace('8990', str(self.mock_proxy_port))
        with open(filename, 'wb') as f:
            f.write(data)

    def __enter__(self):
        self.mockserver = MockServer(
            self.mock_http_port,
            self.mock_https_port,
            self.mock_proxy_port,
        )
        self.mockserver.__enter__()

        self.splashserver = SplashServer(
            logfile=self.logfile,
            proxy_profiles_path=self.proxy_profiles_path,
            js_profiles_path=self.js_profiles_path,
            filters_path=self.filters_path,
            extra_args = [
                '--lua-package-path', '%s/?.lua' % self.lua_modules.rstrip('/'),
                '--lua-sandbox-allowed-modules', ';'.join(self.lua_sandbox_allowed_modules),
            ]
        )
        self.splashserver.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.splashserver.__exit__(None, None, None)
        self.mockserver.__exit__(None, None, None)
        shutil.rmtree(self.tmp_folder)


def test_path(*args):
    return os.path.join(os.path.dirname(__file__), *args)

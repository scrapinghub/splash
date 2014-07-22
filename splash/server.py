import os, sys, optparse, resource, traceback, signal, time
from psutil import phymem_usage
from splash import defaults

# A global reference must be kept to QApplication, otherwise the process will
# segfault
qtapp = None


def install_qtreactor(verbose):
    global qtapp

    from twisted.python import log
    from PyQt4.QtGui import QApplication
    from PyQt4.QtCore import QAbstractEventDispatcher

    class QApp(QApplication):

        blockedAt = 0

        def __init__(self, *args):
            super(QApp, self).__init__(*args)
            if verbose:
                disp = QAbstractEventDispatcher.instance()
                disp.aboutToBlock.connect(self.aboutToBlock)
                disp.awake.connect(self.awake)

        def aboutToBlock(self):
            self.blockedAt = time.time()
            log.msg("aboutToBlock", system="QAbstractEventDispatcher")

        def awake(self):
            diff = time.time() - self.blockedAt
            log.msg("awake; block time: %0.4f" % diff, system="QAbstractEventDispatcher")

    qtapp = QApp(sys.argv)
    import qt4reactor
    qt4reactor.install()


def parse_opts():
    _bool_default = {True:' (default)', False: ''}

    op = optparse.OptionParser()
    op.add_option("-f", "--logfile", help="log file")
    op.add_option("-m", "--maxrss", type=float, default=0,
        help="exit if max RSS reaches this value (in MB or ratio of physical mem) (default: %default)")
    op.add_option("-p", "--port", type="int", default=defaults.SPLASH_PORT,
        help="port to listen to (default: %default)")
    op.add_option("-s", "--slots", type="int", default=defaults.SLOTS,
        help="number of render slots (default: %default)")
    op.add_option("--proxy-profiles-path",
        help="path to a folder with proxy profiles")
    op.add_option("--js-profiles-path",
        help="path to a folder with javascript profiles")
    op.add_option("--no-js-cross-domain-access",
        action="store_false",
        dest="js_cross_domain_enabled",
        default=not defaults.JS_CROSS_DOMAIN_ENABLED,
        help="disable support for cross domain access when executing custom javascript" + _bool_default[not defaults.JS_CROSS_DOMAIN_ENABLED])
    op.add_option("--js-cross-domain-access",
        action="store_true",
        dest="js_cross_domain_enabled",
        default=defaults.JS_CROSS_DOMAIN_ENABLED,
        help="enable support for cross domain access when executing custom javascript "
             "(WARNING: it could break rendering for some of the websites)" + _bool_default[defaults.JS_CROSS_DOMAIN_ENABLED])
    op.add_option("--no-cache", action="store_false", dest="cache_enabled",
        help="disable local cache" + _bool_default[not defaults.CACHE_ENABLED])
    op.add_option("--cache", action="store_true", dest="cache_enabled",
        help="enable local cache (WARNING: don't enable it unless you know what are you doing)" + _bool_default[defaults.CACHE_ENABLED])
    op.add_option("-c", "--cache-path", help="local cache folder")
    op.add_option("--cache-size", type=int, default=defaults.CACHE_SIZE,
        help="maximum cache size in MB (default: %default)")
    op.add_option("--manhole", action="store_true",
        help="enable manhole server")
    op.add_option("--disable-proxy", action="store_true", default=False,
        help="disable proxy server")
    op.add_option("--proxy-portnum", type="int", default=defaults.PROXY_PORT,
        help="proxy port to listen to (default: %default)")
    op.add_option('--allowed-schemes', default=",".join(defaults.ALLOWED_SCHEMES),
        help="comma-separated list of allowed URI schemes (defaut: %default)")
    op.add_option("--filters-path",
        help="path to a folder with network request filters")
    op.add_option("-v", "--verbosity", type=int, default=defaults.VERBOSITY,
        help="verbosity level; valid values are integers from 0 to 5")

    return op.parse_args()


def start_logging(opts):
    import twisted
    from twisted.python import log
    from twisted.python.logfile import DailyLogFile
    if opts.logfile:
        logfile = DailyLogFile.fromFullPath(opts.logfile)
    else:
        logfile = sys.stderr
    flo = log.startLogging(logfile)

    if twisted.version.major >= 13:  # add microseconds to log
        flo.timeFormat = "%Y-%m-%d %H:%M:%S.%f%z"


def splash_started(opts, stderr):
    if opts.logfile:
        stderr.write("Splash started - logging to: %s\n" % opts.logfile)


def bump_nofile_limit():
    from twisted.python import log
    log.msg("Open files limit: %d" % resource.getrlimit(resource.RLIMIT_NOFILE)[0])
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    values_to_try = [v for v in [hard, 100000, 10000] if v > soft]
    for new_soft in values_to_try:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
        except ValueError:
            continue
        else:
            log.msg("Open files limit increased from %d to %d" % (soft, new_soft))
            break
    else:
        log.msg("Can't bump open files limit")


def manhole_server(portnum=None, username=None, password=None):
    from twisted.internet import reactor
    from twisted.manhole import telnet

    f = telnet.ShellFactory()
    f.username = defaults.MANHOLE_USERNAME if username is None else username
    f.password = defaults.MANHOLE_PASSWORD if password is None else password
    portnum = defaults.MANHOLE_PORT if portnum is None else portnum
    reactor.listenTCP(portnum, f)


def splash_server(portnum, slots, network_manager, get_splash_proxy_factory=None,
                  js_profiles_path=None, disable_proxy=False, proxy_portnum=None,
                  verbosity=None):
    from twisted.internet import reactor
    from twisted.web.server import Site
    from splash.resources import Root
    from splash.pool import RenderPool
    from twisted.python import log

    verbosity = defaults.VERBOSITY if verbosity is None else verbosity
    log.msg("verbosity=%d" % verbosity)

    slots = defaults.SLOTS if slots is None else slots
    log.msg("slots=%s" % slots)

    pool = RenderPool(
        slots=slots,
        network_manager=network_manager,
        get_splash_proxy_factory=get_splash_proxy_factory,
        js_profiles_path=js_profiles_path,
        verbosity=verbosity,
    )

    # HTTP API
    root = Root(pool)
    factory = Site(root)
    reactor.listenTCP(portnum, factory)

    # HTTP Proxy
    if disable_proxy is False:
        from splash.proxy_server import SplashProxyFactory
        splash_proxy_factory = SplashProxyFactory(pool)
        proxy_portnum = defaults.PROXY_PORT if proxy_portnum is None else proxy_portnum
        reactor.listenTCP(proxy_portnum, splash_proxy_factory)


def monitor_maxrss(maxrss):
    from twisted.internet import reactor, task
    from twisted.python import log
    from splash.utils import get_ru_maxrss

    # Support maxrss as a ratio of total physical memory
    if 0.0 < maxrss < 1.0:
        maxrss = phymem_usage().total * maxrss / (1024 ** 2)

    def check_maxrss():
        if get_ru_maxrss() > maxrss * (1024 ** 2):
            log.msg("maxrss exceeded %d MB, shutting down..." % maxrss)
            reactor.stop()

    if maxrss:
        log.msg("maxrss limit: %d MB" % maxrss)
        t = task.LoopingCall(check_maxrss)
        t.start(60, now=False)


def default_splash_server(portnum, slots=None,
                          cache_enabled=None, cache_path=None, cache_size=None,
                          proxy_profiles_path=None, js_profiles_path=None,
                          js_disable_cross_domain_access=False,
                          disable_proxy=False, proxy_portnum=None,
                          filters_path=None, allowed_schemes=None,
                          verbosity=None):
    from splash import network_manager
    verbosity = defaults.VERBOSITY if verbosity is None else verbosity
    if allowed_schemes is None:
        allowed_schemes = defaults.ALLOWED_SCHEMES
    else:
        allowed_schemes = allowed_schemes.split(',')
    manager = network_manager.SplashQNetworkAccessManager(
        filters_path=filters_path,
        allowed_schemes=allowed_schemes,
        verbosity=verbosity
    )
    manager.setCache(_default_cache(cache_enabled, cache_path, cache_size))
    get_splash_proxy_factory = _default_proxy_config(proxy_profiles_path)
    js_profiles_path = _check_js_profiles_path(js_profiles_path)
    _set_global_render_settings(js_disable_cross_domain_access)
    return splash_server(portnum, slots, manager, get_splash_proxy_factory,
                         js_profiles_path, disable_proxy, proxy_portnum,
                         verbosity)


def _default_cache(cache_enabled, cache_path, cache_size):
    from twisted.python import log
    from splash import cache

    cache_enabled = defaults.CACHE_ENABLED if cache_enabled is None else cache_enabled
    cache_path = defaults.CACHE_PATH if cache_path is None else cache_path
    cache_size = defaults.CACHE_SIZE if cache_size is None else cache_size

    if cache_enabled:
        log.msg("cache_enabled=%s, cache_path=%r, cache_size=%sMB" % (cache_enabled, cache_path, cache_size))
        log.msg("[WARNING] You have enabled cache support. QT cache is known "
                "to cause segfaults and other issues for splash; "
                "enable it on your own risk. We recommend using a separate "
                "caching forward proxy like squid.")
        return cache.construct(cache_path, cache_size)


def _default_proxy_config(proxy_profiles_path):
    from twisted.python import log
    from splash import proxy

    if proxy_profiles_path is not None and not os.path.isdir(proxy_profiles_path):
        log.msg("--proxy-profiles-path does not exist or it is not a folder; "
                "proxy won't be used")
        proxy_enabled = False
    else:
        proxy_enabled = proxy_profiles_path is not None

    if proxy_enabled:
        log.msg("proxy support is enabled, proxy profiles path: %s" % proxy_profiles_path)
        def get_splash_proxy_factory(request):
            return proxy.ProfilesSplashProxyFactory(proxy_profiles_path, request)
        return get_splash_proxy_factory


def _check_js_profiles_path(js_profiles_path):
    from twisted.python import log

    if js_profiles_path is not None and not os.path.isdir(js_profiles_path):
        log.msg("--js-profiles-path does not exist or it is not a folder; "
                "js profiles won't be used")
    return js_profiles_path


def _set_global_render_settings(js_disable_cross_domain_access):
    from PyQt4.QtWebKit import QWebSecurityOrigin
    if js_disable_cross_domain_access is False:
        # In order to enable cross domain requests it is necessary to add
        # the http and https to the local scheme, this way all the urls are
        # seen as inside the same security origin.
        for scheme in ['http', 'https']:
            QWebSecurityOrigin.addLocalScheme(scheme)


def main():
    opts, _ = parse_opts()

    install_qtreactor(opts.verbosity >= 5)

    start_logging(opts)
    bump_nofile_limit()
    monitor_maxrss(opts.maxrss)
    if opts.manhole:
        manhole_server()

    default_splash_server(portnum=opts.port,
                  slots=opts.slots,
                  cache_enabled=opts.cache_enabled,
                  cache_path=opts.cache_path,
                  cache_size=opts.cache_size,
                  proxy_profiles_path=opts.proxy_profiles_path,
                  js_profiles_path=opts.js_profiles_path,
                  js_disable_cross_domain_access=not opts.js_cross_domain_enabled,
                  disable_proxy=opts.disable_proxy,
                  proxy_portnum=opts.proxy_portnum,
                  filters_path=opts.filters_path,
                  allowed_schemes=opts.allowed_schemes,
                  verbosity=opts.verbosity)
    signal.signal(signal.SIGUSR1, lambda s, f: traceback.print_stack(f))

    from twisted.internet import reactor
    reactor.callWhenRunning(splash_started, opts, sys.stderr)
    reactor.run()


if __name__ == "__main__":
    main()

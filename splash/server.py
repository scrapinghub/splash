import os, sys, optparse, resource, traceback, signal
from splash import defaults

# A global reference must be kept to QApplication, otherwise the process will
# segfault
qtapp = None


def install_qtreactor():
    global qtapp

    from PyQt4.QtGui import QApplication
    qtapp = QApplication(sys.argv)
    import qt4reactor
    qt4reactor.install()


def parse_opts():
    op = optparse.OptionParser()
    op.add_option("-f", "--logfile", help="log file")
    op.add_option("-m", "--maxrss", type=float, default=0,
        help="exit if max RSS reaches this value (in MB) (default: %default)")
    op.add_option("-p", "--port", type="int", default=defaults.SPLASH_PORT,
        help="port to listen to (default: %default)")
    op.add_option("-s", "--slots", type="int", default=defaults.SLOTS,
        help="number of render slots (default: %default)")
    op.add_option("--proxy-profiles-path",
        help="path to a folder with proxy profiles")
    _bool_default={True:' (active by default)', False: ''}
    op.add_option("--cache", action="store_true", dest="cache_enabled",
        help="enable local cache" + _bool_default[defaults.CACHE_ENABLED])
    op.add_option("--no-cache", action="store_false", dest="cache_enabled",
        help="disable local cache" + _bool_default[not defaults.CACHE_ENABLED])
    op.add_option("-c", "--cache-path", help="local cache folder")
    op.add_option("--cache-size", type=int, default=defaults.CACHE_SIZE,
        help="maximum cache size in MB (default: %default)")
    op.add_option("--manhole", action="store_true",
        help="enable manhole server")

    return op.parse_args()


def start_logging(opts):
    from twisted.python import log
    from twisted.python.logfile import DailyLogFile
    if opts.logfile:
        logfile = DailyLogFile.fromFullPath(opts.logfile)
    else:
        logfile = sys.stderr
    log.startLogging(logfile)


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


def splash_server(portnum, slots, network_manager, get_splash_proxy_factory=None):
    from twisted.internet import reactor
    from twisted.web.server import Site
    from splash.resources import Root
    from splash.pool import RenderPool
    from twisted.python import log

    slots = defaults.SLOTS if slots is None else slots
    log.msg("slots=%s" % slots)

    pool = RenderPool(
        slots=slots,
        network_manager=network_manager,
        get_splash_proxy_factory=get_splash_proxy_factory
    )
    root = Root(pool)
    factory = Site(root)
    reactor.listenTCP(portnum, factory)


def monitor_maxrss(maxrss):
    from twisted.internet import reactor, task
    from twisted.python import log
    def check_maxrss():
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > maxrss * 1024:
            log.msg("maxrss exceeded %d MB, shutting down..." % maxrss)
            reactor.stop()
    if maxrss:
        log.msg("maxrss limit: %d MB" % maxrss)
        t = task.LoopingCall(check_maxrss)
        t.start(60, now=False)


def default_splash_server(portnum, slots=None,
                          cache_enabled=None, cache_path=None, cache_size=None,
                          proxy_profiles_path=None):
    from splash import network_manager
    manager = network_manager.FilteringQNetworkAccessManager()
    manager.setCache(_default_cache(cache_enabled, cache_path, cache_size))
    get_splash_proxy_factory = _default_proxy_config(proxy_profiles_path)
    return splash_server(portnum, slots, manager, get_splash_proxy_factory)


def _default_cache(cache_enabled, cache_path, cache_size):
    from twisted.python import log
    from splash import cache

    cache_enabled = defaults.CACHE_ENABLED if cache_enabled is None else cache_enabled
    cache_path = defaults.CACHE_PATH if cache_path is None else cache_path
    cache_size = defaults.CACHE_SIZE if cache_size is None else cache_size

    log.msg("cache_enabled=%s, cache_path=%r, cache_size=%sMB" % (cache_enabled, cache_path, cache_size))

    if cache_enabled:
        return cache.construct(cache_path, cache_size)


def _default_proxy_config(proxy_profiles_path):
    from twisted.python import log
    from splash import proxy

    if proxy_profiles_path is not None and not os.path.isdir(proxy_profiles_path):
        log.msg("--proxy-profiles-path does not exist or it is not a folder; proxy won't be used")
        proxy_enabled = False
    else:
        proxy_enabled = proxy_profiles_path is not None

    if proxy_enabled:
        log.msg("proxy support is enabled, proxy profiles path: %s" % proxy_profiles_path)
        def get_splash_proxy_factory(request):
            return proxy.ProfilesSplashProxyFactory(proxy_profiles_path, request)
        return get_splash_proxy_factory


def main():
    install_qtreactor()
    opts, _ = parse_opts()

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
                  proxy_profiles_path=opts.proxy_profiles_path)
    signal.signal(signal.SIGUSR1, lambda s, f: traceback.print_stack(f))

    from twisted.internet import reactor
    reactor.callWhenRunning(splash_started, opts, sys.stderr)
    reactor.run()


if __name__ == "__main__":
    main()

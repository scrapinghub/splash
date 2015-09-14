from __future__ import absolute_import
import os
import sys
import optparse
import resource
import traceback
import signal
import functools

from splash import defaults, __version__
from splash import xvfb
from splash.qtutils import init_qt_app

def install_qtreactor(verbose):
    init_qt_app(verbose)
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
    op.add_option("--max-timeout", type="float", default=defaults.MAX_TIMEOUT,
        help="maximum allowed value for timeout (default: %default)")
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
    op.add_option("--disable-ui", action="store_true", default=False,
        help="disable web UI")
    op.add_option("--proxy-portnum", type="int", default=defaults.PROXY_PORT,
        help="proxy port to listen to (default: %default)")
    op.add_option('--allowed-schemes', default=",".join(defaults.ALLOWED_SCHEMES),
        help="comma-separated list of allowed URI schemes (defaut: %default)")
    op.add_option("--filters-path",
        help="path to a folder with network request filters")
    op.add_option("--disable-xvfb", action="store_true", default=False,
        help="disable Xvfb auto start")
    op.add_option("--disable-lua", action="store_true", default=False,
        help="disable Lua scripting")
    op.add_option("--disable-lua-sandbox", action="store_true", default=False,
        help="disable Lua sandbox")
    op.add_option("--lua-package-path", default="",
        help="semicolon-separated places to add to Lua package.path. "
             "Each place can have a ? in it that's replaced with the module name.")
    op.add_option("--lua-sandbox-allowed-modules", default="",
        help="semicolon-separated list of Lua module names allowed to be required from a sandbox.")
    op.add_option("-v", "--verbosity", type=int, default=defaults.VERBOSITY,
        help="verbosity level; valid values are integers from 0 to 5 (default: %default)")
    op.add_option("--version", action="store_true",
        help="print Splash version number and exit")

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


def log_splash_version():
    import twisted
    from twisted.python import log
    from splash import lua
    from splash.qtutils import get_versions

    log.msg("Splash version: %s" % __version__)

    verdict = get_versions()
    versions = [
        "Qt %s" % verdict['qt'],
        "PyQt %s" % verdict['pyqt'],
        "WebKit %s" % verdict['webkit'],
        "sip %s" % verdict['sip'],
        "Twisted %s" % twisted.version.short(),
    ]

    if lua.is_supported():
        versions.append(lua.get_version())

    log.msg(", ".join(versions))
    log.msg("Python %s" % sys.version.replace("\n", ""))


def manhole_server(portnum=None, username=None, password=None):
    from twisted.internet import reactor
    from twisted.manhole import telnet

    f = telnet.ShellFactory()
    f.username = defaults.MANHOLE_USERNAME if username is None else username
    f.password = defaults.MANHOLE_PASSWORD if password is None else password
    portnum = defaults.MANHOLE_PORT if portnum is None else portnum
    reactor.listenTCP(portnum, f)


def splash_server(portnum, slots, network_manager, max_timeout,
                  splash_proxy_factory_cls=None,
                  js_profiles_path=None, disable_proxy=False, proxy_portnum=None,
                  ui_enabled=True,
                  lua_enabled=True,
                  lua_sandbox_enabled=True,
                  lua_package_path="",
                  lua_sandbox_allowed_modules=(),
                  verbosity=None):
    from twisted.internet import reactor
    from twisted.web.server import Site
    from splash.resources import Root
    from splash.pool import RenderPool
    from twisted.python import log
    from splash import lua

    verbosity = defaults.VERBOSITY if verbosity is None else verbosity
    log.msg("verbosity=%d" % verbosity)

    slots = defaults.SLOTS if slots is None else slots
    log.msg("slots=%s" % slots)

    pool = RenderPool(
        slots=slots,
        network_manager=network_manager,
        splash_proxy_factory_cls=splash_proxy_factory_cls,
        js_profiles_path=js_profiles_path,
        verbosity=verbosity,
    )

    if not lua.is_supported() and lua_enabled:
        lua_enabled = False
        log.msg("WARNING: Lua is not available, but --disable-lua option is not passed")

    # HTTP API
    onoff = {True: "enabled", False: "disabled"}
    log.msg(
        "Web UI: %s, Lua: %s (sandbox: %s), Proxy Server: %s" % (
            onoff[ui_enabled],
            onoff[lua_enabled],
            onoff[lua_sandbox_enabled],
            onoff[not disable_proxy],
        )
    )

    root = Root(
        pool=pool,
        ui_enabled=ui_enabled,
        lua_enabled=lua_enabled,
        lua_sandbox_enabled=lua_sandbox_enabled,
        lua_package_path=lua_package_path,
        lua_sandbox_allowed_modules=lua_sandbox_allowed_modules,
        max_timeout=max_timeout
    )
    factory = Site(root)
    reactor.listenTCP(portnum, factory)

    # HTTP Proxy
    if not disable_proxy:
        from splash.proxy_server import SplashProxyServerFactory
        proxy_server_factory = SplashProxyServerFactory(pool, max_timeout=max_timeout)
        proxy_portnum = defaults.PROXY_PORT if proxy_portnum is None else proxy_portnum
        reactor.listenTCP(proxy_portnum, proxy_server_factory)


def monitor_maxrss(maxrss):
    from twisted.internet import reactor, task
    from twisted.python import log
    from splash.utils import get_ru_maxrss, get_total_phymem

    # Support maxrss as a ratio of total physical memory
    if 0.0 < maxrss < 1.0:
        maxrss = get_total_phymem() * maxrss / (1024 ** 2)

    def check_maxrss():
        if get_ru_maxrss() > maxrss * (1024 ** 2):
            log.msg("maxrss exceeded %d MB, shutting down..." % maxrss)
            reactor.stop()

    if maxrss:
        log.msg("maxrss limit: %d MB" % maxrss)
        t = task.LoopingCall(check_maxrss)
        t.start(60, now=False)


def default_splash_server(portnum, max_timeout, slots=None,
                          cache_enabled=None, cache_path=None, cache_size=None,
                          proxy_profiles_path=None, js_profiles_path=None,
                          js_disable_cross_domain_access=False,
                          disable_proxy=False, proxy_portnum=None,
                          filters_path=None, allowed_schemes=None,
                          ui_enabled=True,
                          lua_enabled=True,
                          lua_sandbox_enabled=True,
                          lua_package_path="",
                          lua_sandbox_allowed_modules=(),
                          verbosity=None):
    from splash import network_manager
    manager = network_manager.create_default(
        filters_path=filters_path,
        verbosity=verbosity,
        allowed_schemes=allowed_schemes,
    )
    manager.setCache(_default_cache(cache_enabled, cache_path, cache_size))
    splash_proxy_factory_cls = _default_proxy_factory(proxy_profiles_path)
    js_profiles_path = _check_js_profiles_path(js_profiles_path)
    _set_global_render_settings(js_disable_cross_domain_access)
    return splash_server(
        portnum=portnum,
        slots=slots,
        network_manager=manager,
        splash_proxy_factory_cls=splash_proxy_factory_cls,
        js_profiles_path=js_profiles_path,
        disable_proxy=disable_proxy,
        proxy_portnum=proxy_portnum,
        ui_enabled=ui_enabled,
        lua_enabled=lua_enabled,
        lua_sandbox_enabled=lua_sandbox_enabled,
        lua_package_path=lua_package_path,
        lua_sandbox_allowed_modules=lua_sandbox_allowed_modules,
        verbosity=verbosity,
        max_timeout=max_timeout
    )


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


def _default_proxy_factory(proxy_profiles_path):
    from twisted.python import log
    from splash import proxy

    if proxy_profiles_path is not None:
        if os.path.isdir(proxy_profiles_path):
            log.msg("proxy profiles support is enabled, "
                    "proxy profiles path: %s" % proxy_profiles_path)
        else:
            log.msg("--proxy-profiles-path does not exist or it is not a folder; "
                    "proxy won't be used")
            proxy_profiles_path = None

    return functools.partial(proxy.get_factory, proxy_profiles_path)


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
    if opts.version:
        print(__version__)
        sys.exit(0)

    start_logging(opts)
    log_splash_version()
    bump_nofile_limit()

    with xvfb.autostart(opts.disable_xvfb) as x:
        xvfb.log_options(x)

        install_qtreactor(opts.verbosity >= 5)

        monitor_maxrss(opts.maxrss)
        if opts.manhole:
            manhole_server()

        default_splash_server(
            portnum=opts.port,
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
            ui_enabled=not opts.disable_ui,
            lua_enabled=not opts.disable_lua,
            lua_sandbox_enabled=not opts.disable_lua_sandbox,
            lua_package_path=opts.lua_package_path.strip(";"),
            lua_sandbox_allowed_modules=opts.lua_sandbox_allowed_modules.split(";"),
            verbosity=opts.verbosity,
            max_timeout=opts.max_timeout
        )
        signal.signal(signal.SIGUSR1, lambda s, f: traceback.print_stack(f))

        from twisted.internet import reactor
        reactor.callWhenRunning(splash_started, opts, sys.stderr)
        reactor.run()


if __name__ == "__main__":
    main()

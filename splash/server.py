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
    import qt5reactor
    qt5reactor.install()


def parse_opts(jupyter=False, argv=sys.argv):
    _bool_default = {True:' (default)', False: ''}

    op = optparse.OptionParser()
    op.add_option("-f", "--logfile", help="log file")
    op.add_option("-m", "--maxrss", type=float, default=0,
        help="exit if max RSS reaches this value (in MB or ratio of physical mem) (default: %default)")
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
    op.add_option('--allowed-schemes', default=",".join(defaults.ALLOWED_SCHEMES),
        help="comma-separated list of allowed URI schemes (defaut: %default)")
    op.add_option("--filters-path",
        help="path to a folder with network request filters")
    op.add_option("--disable-private-mode", action="store_true", default=not defaults.PRIVATE_MODE,
        help="disable private mode (WARNING: data may leak between requests)" + _bool_default[not defaults.PRIVATE_MODE])
    op.add_option("--disable-xvfb", action="store_true", default=False,
        help="disable Xvfb auto start")
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

    if not jupyter:
        # This options are specific of splash server and not used in splash-jupyter
        op.add_option("-p", "--port", type="int", default=defaults.SPLASH_PORT,
            help="port to listen to (default: %default)")
        op.add_option("-s", "--slots", type="int", default=defaults.SLOTS,
            help="number of render slots (default: %default)")
        op.add_option("--max-timeout", type="float", default=defaults.MAX_TIMEOUT,
            help="maximum allowed value for timeout (default: %default)")
        op.add_option("--manhole", action="store_true",
            help="enable manhole server")
        op.add_option("--disable-ui", action="store_true", default=False,
            help="disable web UI")
        op.add_option("--disable-lua", action="store_true", default=False,
            help="disable Lua scripting")
        op.add_option("--argument-cache-max-entries", type="int",
            default=defaults.ARGUMENT_CACHE_MAX_ENTRIES,
            help="maximum number of entries in arguments cache (default: %default)")

    opts, args = op.parse_args(argv)

    if jupyter:
        opts.manhole = False
        opts.disable_ui = True
        opts.disable_lua = False
        opts.port = None
        opts.slots = None
        opts.max_timeout = None
        opts.argument_cache_max_entries = None

    return opts, args


def start_logging(opts):
    import twisted
    from twisted.python import log
    if opts.logfile:
        from twisted.python.logfile import DailyLogFile
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


def splash_server(portnum, slots, network_manager_factory, max_timeout,
                  splash_proxy_factory_cls=None,
                  js_profiles_path=None,
                  ui_enabled=True,
                  lua_enabled=True,
                  lua_sandbox_enabled=True,
                  lua_package_path="",
                  lua_sandbox_allowed_modules=(),
                  argument_cache_max_entries=None,
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

    if argument_cache_max_entries:
        log.msg("argument_cache_max_entries=%s" % argument_cache_max_entries)

    pool = RenderPool(
        slots=slots,
        network_manager_factory=network_manager_factory,
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
        "Web UI: %s, Lua: %s (sandbox: %s)" % (
            onoff[ui_enabled],
            onoff[lua_enabled],
            onoff[lua_sandbox_enabled],
        )
    )

    root = Root(
        pool=pool,
        ui_enabled=ui_enabled,
        lua_enabled=lua_enabled,
        lua_sandbox_enabled=lua_sandbox_enabled,
        lua_package_path=lua_package_path,
        lua_sandbox_allowed_modules=lua_sandbox_allowed_modules,
        max_timeout=max_timeout,
        argument_cache_max_entries=argument_cache_max_entries,
    )
    factory = Site(root)
    reactor.listenTCP(portnum, factory)


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

            # XXX: for some reason twisted qt5 reactor can stop without
            # finishing the Python process. This is a hack to exit anyways.
            def force_shutdown():
                log.msg("Reactor didn't stop cleanly, doing unclean shutdown.")
                os._exit(0)
            reactor.callLater(2.0, force_shutdown)

            reactor.stop()

    if maxrss:
        log.msg("maxrss limit: %d MB" % maxrss)
        t = task.LoopingCall(check_maxrss)
        t.start(60, now=False)


def default_splash_server(portnum, max_timeout, slots=None,
                          proxy_profiles_path=None, js_profiles_path=None,
                          js_disable_cross_domain_access=False,
                          filters_path=None, allowed_schemes=None,
                          private_mode=True,
                          ui_enabled=True,
                          lua_enabled=True,
                          lua_sandbox_enabled=True,
                          lua_package_path="",
                          lua_sandbox_allowed_modules=(),
                          argument_cache_max_entries=None,
                          verbosity=None,
                          server_factory=splash_server):
    from splash import network_manager
    network_manager_factory = network_manager.NetworkManagerFactory(
        filters_path=filters_path,
        verbosity=verbosity,
        allowed_schemes=allowed_schemes,
    )
    splash_proxy_factory_cls = _default_proxy_factory(proxy_profiles_path)
    js_profiles_path = _check_js_profiles_path(js_profiles_path)
    _set_global_render_settings(js_disable_cross_domain_access, private_mode)
    return server_factory(
        portnum=portnum,
        slots=slots,
        network_manager_factory=network_manager_factory,
        splash_proxy_factory_cls=splash_proxy_factory_cls,
        js_profiles_path=js_profiles_path,
        ui_enabled=ui_enabled,
        lua_enabled=lua_enabled,
        lua_sandbox_enabled=lua_sandbox_enabled,
        lua_package_path=lua_package_path,
        lua_sandbox_allowed_modules=lua_sandbox_allowed_modules,
        verbosity=verbosity,
        max_timeout=max_timeout,
        argument_cache_max_entries=argument_cache_max_entries,
    )


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


def _set_global_render_settings(js_disable_cross_domain_access, private_mode):
    from PyQt5.QtWebKit import QWebSecurityOrigin, QWebSettings

    if js_disable_cross_domain_access is False:
        # In order to enable cross domain requests it is necessary to add
        # the http and https to the local scheme, this way all the urls are
        # seen as inside the same security origin.
        for scheme in ['http', 'https']:
            QWebSecurityOrigin.addLocalScheme(scheme)

    settings = QWebSettings.globalSettings()
    settings.setAttribute(QWebSettings.PrivateBrowsingEnabled, private_mode)
    settings.setAttribute(QWebSettings.LocalStorageEnabled, not private_mode)


def main(jupyter=False, argv=sys.argv, server_factory=splash_server):
    opts, _ = parse_opts(jupyter, argv)
    if opts.version:
        print(__version__)
        sys.exit(0)

    if not jupyter:
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
            proxy_profiles_path=opts.proxy_profiles_path,
            js_profiles_path=opts.js_profiles_path,
            js_disable_cross_domain_access=not opts.js_cross_domain_enabled,
            filters_path=opts.filters_path,
            allowed_schemes=opts.allowed_schemes,
            private_mode=not opts.disable_private_mode,
            ui_enabled=not opts.disable_ui,
            lua_enabled=not opts.disable_lua,
            lua_sandbox_enabled=not opts.disable_lua_sandbox,
            lua_package_path=opts.lua_package_path.strip(";"),
            lua_sandbox_allowed_modules=opts.lua_sandbox_allowed_modules.split(";"),
            verbosity=opts.verbosity,
            max_timeout=opts.max_timeout,
            argument_cache_max_entries=opts.argument_cache_max_entries,
            server_factory=server_factory,
        )
        signal.signal(signal.SIGUSR1, lambda s, f: traceback.print_stack(f))

        if not jupyter:
            from twisted.internet import reactor
            reactor.callWhenRunning(splash_started, opts, sys.stderr)
            reactor.run()


if __name__ == "__main__":
    main()

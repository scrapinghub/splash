import sys, optparse, resource, traceback, signal

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
    op.add_option("-m", "--maxrss", type="int", default=0,
        help="exit if max RSS reaches this value (in KB) (default: %default)")
    op.add_option("-p", "--port", type="int", default=8050,
        help="port to listen to (default: %default)")
    return op.parse_args()

def start_logging(opts):
    from twisted.python import log
    from twisted.python.logfile import DailyLogFile
    if opts.logfile:
        logfile = DailyLogFile.fromFullPath(opts.logfile)
    else:
        logfile = sys.stderr
    log.startLogging(logfile)
    log.msg("Open files limit: %d" % resource.getrlimit(resource.RLIMIT_NOFILE)[0])

def splash_started(opts, stderr):
    if opts.logfile:
        stderr.write("Splash started - logging to: %s\n" % opts.logfile)

def bump_nofile_limit():
    _, n = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (n, n))

def manhole_server():
    from twisted.internet import reactor
    from twisted.manhole import telnet

    f = telnet.ShellFactory()
    f.username = "admin"
    f.password = "admin"
    reactor.listenTCP(5023, f)

def splash_server(portnum):
    from twisted.internet import reactor
    from twisted.web.server import Site
    from splash.resources import Root
    from splash.pool import RenderPool

    pool = RenderPool()
    root = Root(pool)
    factory = Site(root)
    reactor.listenTCP(portnum, factory)

def monitor_maxrss(maxrss):
    from twisted.internet import reactor, task
    from twisted.python import log
    def check_maxrss():
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > maxrss:
            log.msg("maxrss exceeded %d kb, shutting down..." % maxrss)
            reactor.stop()
    if maxrss:
        log.msg("maxrss limit: %d kb" % maxrss)
        t = task.LoopingCall(check_maxrss)
        t.start(60, now=False)

def main():
    install_qtreactor()
    opts, _ = parse_opts()

    bump_nofile_limit()
    start_logging(opts)
    monitor_maxrss(opts.maxrss)
    manhole_server()
    splash_server(opts.port)
    signal.signal(signal.SIGUSR1, lambda s, f: traceback.print_stack(f))

    from twisted.internet import reactor
    reactor.callWhenRunning(splash_started, opts, sys.stderr)
    reactor.run()

if __name__ == "__main__":
    main()

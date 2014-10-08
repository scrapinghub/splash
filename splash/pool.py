from twisted.internet import defer
from twisted.python import log


class RenderPool(object):
    """A pool of renders. The number of slots determines how many
    renders will be run in parallel, at the most."""

    def __init__(self, slots, network_manager, get_splash_proxy_factory, js_profiles_path, verbosity=1):
        self.network_manager = network_manager
        self.get_splash_proxy_factory = get_splash_proxy_factory
        self.js_profiles_path = js_profiles_path
        self.active = set()
        self.queue = defer.DeferredQueue()
        self.verbosity = verbosity
        for n in range(slots):
            self._wait_for_render(None, n, log=False)

    def render(self, rendercls, splash_request, **kwargs):
        if self.get_splash_proxy_factory:
            splash_proxy_factory = self.get_splash_proxy_factory(splash_request)
        else:
            splash_proxy_factory = None

        pool_d = defer.Deferred()
        self.log("queued %s" % id(splash_request))
        self.queue.put((rendercls, splash_request, splash_proxy_factory, kwargs, pool_d))
        return pool_d

    def _wait_for_render(self, _, slot, log=True):
        if log:
            self.log("SLOT %d is available" % slot)
        d = self.queue.get()
        d.addCallback(self._start_render, slot)
        d.addBoth(self._wait_for_render, slot)
        return _

    def _start_render(self, (rendercls, splash_request, splash_proxy_factory, kwargs, pool_d), slot):
        self.log("initializing SLOT %d" % (slot, ))
        render = rendercls(
            network_manager=self.network_manager,
            splash_proxy_factory=splash_proxy_factory,
            splash_request=splash_request,
            verbosity=self.verbosity,
        )
        self.active.add(render)
        render.deferred.chainDeferred(pool_d)
        pool_d.addErrback(self._error, render, slot)
        pool_d.addBoth(self._close_render, render, slot)

        self.log("SLOT %d is creating request %s" % (slot, id(splash_request)))
        render.doRequest(**kwargs)
        self.log("SLOT %d is working on %s" % (slot, id(splash_request)))

        return render.deferred

    def _error(self, _, render, slot):
        self.log("SLOT %d finished with an error %s %s" % (slot, id(render.splash_request), render))
        return _

    def _close_render(self, _, render, slot):
        self.log("SLOT %d is closing %s %s" % (slot, id(render.splash_request), render))
        self.active.remove(render)
        render.deferred.cancel()
        render.close()
        self.log("SLOT %d done with %s %s" % (slot, id(render.splash_request), render))
        return _

    def log(self, text):
        if self.verbosity >= 2:
            log.msg(text, system='pool')

from twisted.internet import defer
from twisted.python import log


class RenderPool(object):
    """A pool of renders. The number of slots determines how many
    renders will be run in parallel, at the most."""

    def __init__(self, slots, network_manager, get_splash_proxy_factory, verbose=0):
        self.network_manager = network_manager
        self.get_splash_proxy_factory = get_splash_proxy_factory
        self.active = set()
        self.queue = defer.DeferredQueue()
        self.verbose = verbose
        for n in range(slots):
            self._wait_for_render(None, n)

    def render(self, rendercls, request, *args):
        if self.get_splash_proxy_factory:
            splash_proxy_factory = self.get_splash_proxy_factory(request)
        else:
            splash_proxy_factory = None

        pool_d = defer.Deferred()
        self.log("queued %s" % id(request))
        self.queue.put((rendercls, request, splash_proxy_factory, args, pool_d))
        return pool_d

    def _wait_for_render(self, _, slot):
        self.log("SLOT %d available" % slot)
        d = self.queue.get()
        d.addCallback(self._start_render, slot)
        d.addBoth(self._wait_for_render, slot)
        return _

    def _start_render(self, (rendercls, request, splash_proxy_factory, args, pool_d), slot):
        render = rendercls(
            network_manager=self.network_manager,
            splash_proxy_factory=splash_proxy_factory,
            splash_request=request,
            verbose=self.verbose >= 2,
        )
        render.doRequest(*args)
        self.active.add(render)

        render.deferred.chainDeferred(pool_d)
        pool_d.addBoth(self._close_render, render, slot)
        self.log("SLOT %d is working on %s" % (slot, id(request)))
        return render.deferred

    def _close_render(self, _, render, slot):
        self.log("SLOT %d finished %s %s" % (slot, id(render.splash_request), render))
        self.active.remove(render)
        render.deferred.cancel()
        render.close()
        return _

    def log(self, text):
        if self.verbose:
            log.msg(text, system='pool')

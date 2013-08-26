from twisted.internet import defer

class RenderPool(object):
    """A pool of renders. The number of slots determines how many
    renders will be run in parallel, at the most."""

    def __init__(self, slots, get_cache=None, get_proxy_factory=None):
        self.get_cache = get_cache or (lambda request: None)
        self.get_proxy_factory = get_proxy_factory or (lambda request: None)
        self.active = set()
        self.queue = defer.DeferredQueue()
        for n in range(slots):
            self._wait_for_render(None, n)

    def render(self, rendercls, request, *args):
        cache = self.get_cache(request)
        proxy_factory = self.get_proxy_factory(request)
        extdef = defer.Deferred()
        self.queue.put((rendercls, cache, proxy_factory, args, extdef))
        return extdef

    def _wait_for_render(self, _, slot):
        d = self.queue.get()
        d.addCallback(self._start_render)
        d.addBoth(self._wait_for_render, slot)
        return _

    def _start_render(self, (rendercls, cache, proxy_factory, args, extdef)):
        render = rendercls(cache=cache, proxy_factory=proxy_factory)
        render.doRequest(*args)
        self.active.add(render)
        d = render.deferred
        d.addBoth(self._close_render, render)
        d.chainDeferred(extdef)
        return d

    def _close_render(self, _, render):
        self.active.remove(render)
        render.close()
        return _

from typing import Dict

import attr
from twisted.internet import defer
from twisted.python import log

from splash.render_options import RenderOptions


@attr.s
class SlotArguments:
    rendercls = attr.ib()
    render_options = attr.ib()  # type: RenderOptions
    splash_proxy_factory = attr.ib()
    kwargs = attr.ib()  # type: Dict
    pool_d = attr.ib()  # type: defer.Deferred


class RenderPool(object):
    """A pool of renders. The number of slots determines how many
    renders will be run in parallel, at the most."""

    def __init__(self, slots,
                 network_manager_factory,
                 splash_proxy_factory_cls,
                 js_profiles_path,
                 verbosity=1):
        self.network_manager_factory = network_manager_factory
        self.splash_proxy_factory_cls = splash_proxy_factory_cls or (lambda profile_name: None)
        self.js_profiles_path = js_profiles_path
        self.active = set()
        self.queue = defer.DeferredQueue()
        self.verbosity = verbosity
        for n in range(slots):
            self._wait_for_render(None, n, log=False)

    def render(self, rendercls, render_options, proxy, **kwargs):
        splash_proxy_factory = self.splash_proxy_factory_cls(proxy)
        pool_d = defer.Deferred()
        slot = SlotArguments(
            rendercls=rendercls,
            render_options=render_options,
            splash_proxy_factory=splash_proxy_factory,
            kwargs=kwargs,
            pool_d = pool_d,
        )
        self.queue.put(slot)
        self.log("[%s] queued" % render_options.get_uid())
        return pool_d

    def _wait_for_render(self, _, slot, log=True):
        if log:
            self.log("SLOT %d is available" % slot)
        d = self.queue.get()
        d.addCallback(self._start_render, slot)
        d.addBoth(self._wait_for_render, slot)
        return _

    def _start_render(self, slot_args: SlotArguments, slot):
        self.log("initializing SLOT %d" % (slot, ))
        # FIXME: refactor. network manager only works for webkit.
        render = slot_args.rendercls(
            render_options=slot_args.render_options,
            verbosity=self.verbosity,
            network_manager=self.network_manager_factory(),
            splash_proxy_factory=slot_args.splash_proxy_factory,
        )
        self.active.add(render)
        render.deferred.chainDeferred(slot_args.pool_d)
        slot_args.pool_d.addErrback(self._error, render, slot)
        slot_args.pool_d.addBoth(self._close_render, render, slot)

        self.log("[%s] SLOT %d is starting" % (
            slot_args.render_options.get_uid(), slot))
        try:
            render.start(**slot_args.kwargs)
        except:
            render.deferred.errback()
            raise
        self.log("[%s] SLOT %d is working" % (
            slot_args.render_options.get_uid(), slot))

        return render.deferred

    def _error(self, failure, render, slot):
        uid = render.render_options.get_uid()
        self.log("[%s] SLOT %d finished with an error %s: %s" % (uid, slot, render, failure))
        return failure

    def _close_render(self, _, render, slot):
        uid = render.render_options.get_uid()
        self.log("[%s] SLOT %d is closing %s" % (uid, slot, render))
        self.active.remove(render)
        render.deferred.cancel()
        render.close()
        self.log("[%s] SLOT %d done with %s" % (uid, slot, render))
        return _

    def log(self, text):
        if self.verbosity >= 2:
            log.msg(text, system='pool')

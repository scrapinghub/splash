import time, resource, json
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor, defer
from twisted.python import log
from splash2.qtrender import WebkitRender, RenderError
from splash2.utils import getarg, BadRequest


class RenderHtml(Resource):

    isLeaf = True

    def render_GET(self, request):
        url = getarg(request, "url")
        timeout = getarg(request, "timeout", 30, type=float)
        render = WebkitRender(url)
        d = render.deferred
        timer = reactor.callLater(timeout, d.cancel)
        d.addCallback(self._cancelTimer, timer)
        d.addCallback(self._writeOutput, request, url)
        d.addErrback(self._timeoutError, request, render)
        d.addErrback(self._renderError, request)
        d.addErrback(self._internalError, request)
        d.addBoth(self._finishRequest, request)
        request.starttime = time.time()
        return NOT_DONE_YET

    def render(self, request):
        try:
            return Resource.render(self, request)
        except BadRequest as e:
            request.setResponseCode(400)
            return str(e) + "\n"

    def _cancelTimer(self, _, timer):
        timer.cancel()
        return _

    def _writeOutput(self, html, request, url):
        stats = {
            "url": url,
            "rendertime": time.time() - request.starttime,
            "rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
        log.msg(json.dumps(stats), system="stats")
        request.write(html)

    def _timeoutError(self, failure, request, render):
        failure.trap(defer.CancelledError)
        request.setResponseCode(504)
        request.write("Timeout exceeded rendering page\n")
        #render.cancel()

    def _renderError(self, failure, request):
        failure.trap(RenderError)
        request.setResponseCode(502)
        request.write("Error rendering page\n")

    def _internalError(self, failure, request):
        request.setResponseCode(500)
        request.write(failure.getErrorMessage())
        log.err()

    def _finishRequest(self, _, request):
        request.finish()


class Root(Resource):

    def __init__(self):
        Resource.__init__(self)
        self.putChild("render.html", RenderHtml())

    def getChild(self, request, name):
        return self


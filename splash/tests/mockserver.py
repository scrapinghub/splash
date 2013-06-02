from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor
from twisted.internet.task import deferLater
from splash.utils import getarg


class JsRender(Resource):

    isLeaf = True

    def render(self, request):
        return """
<html>
<body>

<p id="p1">Before</p>

<script>
document.getElementById("p1").innerHTML="After";
</script>

</body>
</html>
"""

class JsAlert(Resource):

    isLeaf = True

    def render(self, request):
        return """
<html>
<body>
<p id="p1">Before</p>
<script>
alert("hello");
document.getElementById("p1").innerHTML="After";
</script>
</body>
</html>
"""

class JsConfirm(Resource):

    isLeaf = True

    def render(self, request):
        return """
<html>
<body>
<p id="p1">Before</p>
<script>
confirm("are you sure?");
document.getElementById("p1").innerHTML="After";
</script>
</body>
</html>
"""


class BaseUrl(Resource):

    def render_GET(self, request):
        return """
<html>
<body>
<p id="p1">Before</p>
<script src="script.js"></script>
</body>
</html>
"""

    def getChild(self, name, request):
        if name == "script.js":
            return self.ScriptJs()
        return self


    class ScriptJs(Resource):

        isLeaf = True

        def render_GET(self, request):
            request.setHeader("Content-Type", "application/javascript")
            return 'document.getElementById("p1").innerHTML="After";'

class Delay(Resource):

    isLeaf = True

    def render_GET(self, request):
        n = getarg(request, "n", 1, type=float)
        d = deferLater(reactor, n, lambda: (request, n))
        d.addCallback(self._delayedRender)
        return NOT_DONE_YET

    def _delayedRender(self, (request, n)):
        request.write("Response delayed for %0.3f seconds\n" % n)
        if not request._disconnected:
            request.finish()

class Partial(Resource):

    isLeaf = True

    def render_GET(self, request):
        request.setHeader("Content-Length", "1024")
        d = deferLater(reactor, 0, lambda: request)
        d.addCallback(self._delayedRender)
        return NOT_DONE_YET

    def _delayedRender(self, request):
        request.write("partial content\n")
        request.finish()

class Drop(Partial):

    def _delayedRender(self, request):
        request.write("this connection will be dropped\n")
        request.channel.transport.loseConnection()
        request.finish()

class Root(Resource):

    def __init__(self):
        Resource.__init__(self)
        self.log = []
        self.putChild("jsrender", JsRender())
        self.putChild("jsalert", JsAlert())
        self.putChild("jsconfirm", JsConfirm())
        self.putChild("baseurl", BaseUrl())
        self.putChild("delay", Delay())
        self.putChild("partial", Partial())
        self.putChild("drop", Drop())


if __name__ == "__main__":
    root = Root()
    factory = Site(root)
    port = reactor.listenTCP(8998, factory)
    def print_listening():
        h = port.getHost()
        print "Mock server running at http://%s:%d" % (h.host, h.port)
    reactor.callWhenRunning(print_listening)
    reactor.run()

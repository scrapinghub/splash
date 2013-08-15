import os
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor, ssl
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


class JsInterval(Resource):

    isLeaf = True

    def render(self, request):
        return """
<html><body>
<div id='num'>not started</div>
<script>
var num=0;
setInterval(function(){
    document.getElementById('num').innerHTML = num;
    num += 1;
}, 1);
</script>
</body></html>
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


def _html_resource(html):
    class HtmlResource(Resource):
        isLeaf = True
        def render(self, request):
            return html
    return HtmlResource


class IframeResource(Resource):

    def __init__(self):
        Resource.__init__(self)
        self.putChild("1.html", self.IframeContent1())
        self.putChild("2.html", self.IframeContent2())
        self.putChild("3.html", self.IframeContent3())
        self.putChild("4.html", self.IframeContent4())
        self.putChild("5.html", self.IframeContent5())
        self.putChild("6.html", self.IframeContent6())
        self.putChild("script.js", self.ScriptJs())
        self.putChild("nested.html", self.NestedIframeContent())

    def render(self, request):
        return """
<html>
<head><script src="/iframes/script.js"></script></head>
<body>

<iframe src="/iframes/1.html">
  <p>no iframe 1</p>
</iframe>

<iframe src="/iframes/2.html">
  <p>no iframe 2</p>
</iframe>

<p id="js-iframe">no js iframes</p>
<p id="js-iframe2">no delayed js iframes</p>
<p id="js-iframe3">no js iframes created in window.onload</p>

<script type="text/javascript">
document.getElementById('js-iframe').innerHTML="<iframe src='/iframes/3.html'>js iframes don't work</iframe>"
</script>

<script type="text/javascript">
window.setTimeout(function(){
    document.getElementById('js-iframe2').innerHTML="<iframe src='/iframes/4.html'>delayed js iframes don't work</iframe>";
}, 100);
</script>

<script type="text/javascript">
window.onload = function(){
    document.getElementById('js-iframe3').innerHTML="<iframe src='/iframes/5.html'>js iframes created in window.onload don't work</iframe>";
};
</script>

</body>
</html>
"""

    IframeContent1 = _html_resource("<html><body>iframes work IFRAME_1_OK</body></html>")
    IframeContent2 = _html_resource("""
        <html><body>
        <iframe src="/iframes/nested.html" width=200 height=200>
            <p>nested iframes don't work</p>
        </iframe>
        </body></html>
        """)
    IframeContent3 = _html_resource("<html><body>js iframes work IFRAME_2_OK</body></html>")
    IframeContent4 = _html_resource("<html><body>delayed js iframes work IFRAME_3_OK</body></html>")
    IframeContent5 = _html_resource("<html><body>js iframes created in window.onoad work IFRAME_4_OK</body></html>")
    IframeContent6 = _html_resource("<html><body>js iframes created by document.write in external script work IFRAME_5_OK</body></html>")
    NestedIframeContent = _html_resource("<html><body><p>nested iframes work IFRAME_6_OK</p></body></html>")

    class ScriptJs(Resource):
        isLeaf = True
        def render(self, request):
            request.setHeader("Content-Type", "application/javascript")
            iframe_html = "<iframe src='/iframes/6.html'>js iframe created by document.write in external script doesn't work</iframe>"
            return '''document.write("%s");''' % iframe_html



class Root(Resource):

    def __init__(self):
        Resource.__init__(self)
        self.log = []
        self.putChild("jsrender", JsRender())
        self.putChild("jsalert", JsAlert())
        self.putChild("jsconfirm", JsConfirm())
        self.putChild("jsinterval", JsInterval())
        self.putChild("baseurl", BaseUrl())
        self.putChild("delay", Delay())
        self.putChild("partial", Partial())
        self.putChild("drop", Drop())
        self.putChild("iframes", IframeResource())


def ssl_factory():
    pem = os.path.join(os.path.dirname(__file__), "server.pem")
    return ssl.DefaultOpenSSLContextFactory(pem, pem)


if __name__ == "__main__":
    root = Root()
    factory = Site(root)
    port = reactor.listenTCP(8998, factory)
    sslport = reactor.listenSSL(8999, factory, ssl_factory())
    def print_listening():
        h = port.getHost()
        s = sslport.getHost()
        print "Mock server running at http://%s:%d & https://%s:%d" % \
            (h.host, h.port, s.host, s.port)
    reactor.callWhenRunning(print_listening)
    reactor.run()

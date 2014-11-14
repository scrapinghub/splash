# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import optparse
import base64
import random
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web import proxy, http
from twisted.internet import reactor, ssl
from twisted.internet.task import deferLater


_REQUIRED = object()

def getarg(request, name, default=_REQUIRED, type=str):
    value = request.args.get(name, [None])[0]
    if value is not None:
        if type is not None:
            value = type(value)
        return value
    elif default is _REQUIRED:
        raise Exception("Missing argument: %s" % name)
    else:
        return default


def _html_resource(html):

    class HtmlResource(Resource):
        isLeaf = True

        def __init__(self, http_port=None, https_port=None):
            Resource.__init__(self)
            self.http_port = http_port
            self.https_port = https_port

        def render(self, request):
            return html % dict(
                http_port=self.http_port,
                https_port=self.https_port
            )

    return HtmlResource


JsRender = _html_resource("""
<html>
<body>

<p id="p1">Before</p>

<script>
document.getElementById("p1").innerHTML="After";
</script>

</body>
</html>
""")

JsAlert = _html_resource("""
<html>
<body>
<p id="p1">Before</p>
<script>
alert("hello");
document.getElementById("p1").innerHTML="After";
</script>
</body>
</html>
""")

JsConfirm = _html_resource("""
<html>
<body>
<p id="p1">Before</p>
<script>
confirm("are you sure?");
document.getElementById("p1").innerHTML="After";
</script>
</body>
</html>
""")

JsInterval = _html_resource("""
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
""")


JsViewport = _html_resource("""
<html><body>
<script>
document.write(window.innerWidth);
document.write('x');
document.write(window.innerHeight);
</script>
</body></html>
""")


TallPage = _html_resource("""
<html style='height:2000px'>
<body>Hello</body>
</html>
""")


BadRelatedResource = _html_resource("""
<html>
<body>
<img src="http://non-existing">
</body>
</html>
""")


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


class SlowImage(Resource):
    """ 1x1 black gif that loads n seconds """

    isLeaf = True

    def render_GET(self, request):
        request.setHeader("Content-Type", "image/gif")
        request.write("GIF89a")
        n = getarg(request, "n", 1, type=float)
        d = deferLater(reactor, n, lambda: (request, n))
        d.addCallback(self._delayedRender)
        return NOT_DONE_YET

    def _delayedRender(self, (request, n)):
        # write 1px black gif
        gif_data = b'AQABAIAAAAAAAAAAACH5BAAAAAAALAAAAAABAAEAAAICTAEAOw=='
        request.write(base64.decodestring(gif_data))
        if not request._disconnected:
            request.finish()


class HtmlWithImage(Resource):
    isLeaf = True

    def render_GET(self, request):
        token = random.random()  # prevent caching
        return """<html><body>
        <img width=50 heigth=50 src="/slow.gif?n=0&rnd=%s">
        </body></html>
        """ % token


class IframeResource(Resource):

    def __init__(self, http_port):
        Resource.__init__(self)
        self.putChild("1.html", self.IframeContent1())
        self.putChild("2.html", self.IframeContent2())
        self.putChild("3.html", self.IframeContent3())
        self.putChild("4.html", self.IframeContent4())
        self.putChild("5.html", self.IframeContent5())
        self.putChild("6.html", self.IframeContent6())
        self.putChild("script.js", self.ScriptJs())
        self.putChild("script2.js", self.OtherDomainScript())
        self.putChild("nested.html", self.NestedIframeContent())
        self.http_port = http_port

    def render(self, request):
        return """
<html>
<head>
    <script src="/iframes/script.js"></script>
    <script src="http://0.0.0.0:%s/iframes/script2.js"></script>
</head>
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
""" % self.http_port

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
            iframe_html = " SAME_DOMAIN <iframe src='/iframes/6.html'>js iframe created by document.write in external script doesn't work</iframe>"
            return '''document.write("%s");''' % iframe_html

    class OtherDomainScript(Resource):
        isLeaf = True
        def render(self, request):
            request.setHeader("Content-Type", "application/javascript")
            return "document.write(' OTHER_DOMAIN ');"


class PostResource(Resource):

    def render_POST(self, request):
        code = request.args.get('code', [200])[0]
        request.setResponseCode(int(code))
        headers = request.getAllHeaders()
        payload = request.content.getvalue() if request.content is not None else ''
        return """
<html>
<body>
<p id="p1">From POST</p>
<p id="headers">
%s
</p>
<p id="payload">
%s
</p>
</body>
</html>
""" % (headers, payload)


class GetResource(Resource):

    def render_GET(self, request):
        code = request.args.get('code', [200])[0]
        request.setResponseCode(int(code))
        headers = request.getAllHeaders()
        payload = request.args
        return """
<html>
<body>
<p id="p1">GET request</p>
<p id="headers">
%s
</p>
<p id="arguments">
%s
</p>
</body>
</html>
""" % (headers, payload)


ExternalIFrameResource = _html_resource("""
<html>
<body>
<iframe id='external' src="https://localhost:%(https_port)s/external">
</iframe>
</body>
</html>
""")

ExternalResource = _html_resource("""
<html>
<body>EXTERNAL</body>
</html>
""")


JsRedirect = _html_resource("""
<html><body>
Redirecting now..
<script> window.location = '/jsredirect-target'; </script>
</body></html>
""")

JsRedirectSlowImage = _html_resource("""
<html><body>
Redirecting now..
<img width=10 heigth=10 src="/slow.gif?n=2">
<script> window.location = '/jsredirect-target'; </script>
</body></html>
""")

JsRedirectOnload = _html_resource("""
<html>
<head>
<script>
window.onload = function(){
    window.location = '/jsredirect-target';
}
</script>
</head>
<body>Redirecting on window.load...</body>
</html>
""")

JsRedirectTimer = _html_resource("""
<html>
<head>
<script>
window.setTimeout(function(){
    window.location = '/jsredirect-target';
}, 100);
</script>
</head>
<body>Redirecting on setTimeout callback...</body>
</html>
""")

JsRedirectInfinite = _html_resource("""
<html>
<head><script> window.location = '/jsredirect-infinite2'; </script></head>
<body>Redirecting infinitely, step #1</body>
</html>
""")

JsRedirectInfinite2 = _html_resource("""
<html>
<head><script> window.location = '/jsredirect-infinite'; </script></head>
<body>Redirecting infinitely, step #2</body>
</html>
""")

JsRedirectToJsRedirect = _html_resource("""
<html><body>
Redirecting to an another redirecting page..
<script>
window.location = '/jsredirect';
</script>
</body></html>
""")

JsRedirectToNonExisting = _html_resource("""
<html><body>
Redirecting to non-existing domain..
<script>
window.location = 'http://non-existing';
</script>
</body></html>
""")


JsRedirectTarget = _html_resource("""
<html><body> JS REDIRECT TARGET </body></html>
""")

MetaRedirect0 = _html_resource("""
<html><head>
<meta http-equiv="REFRESH" content="0; URL=/meta-redirect-target/">
</head>
<body></body></html>
""")

MetaRedirectSlowLoad = _html_resource("""
<html><head>
<meta http-equiv="REFRESH" content="0; URL=/meta-redirect-target/">
</head>
<body><img src="/delay?n=0.2"></body></html>
""")

MetaRedirectSlowLoad2 = _html_resource("""
<html><head>
<meta http-equiv="REFRESH" content="0; URL=/meta-redirect-target/">
</head>
<body><img width=10 heigth=10 src="/slow.gif?n=2"></body></html>
""")

MetaRedirect1 = _html_resource("""
<html><head>
<meta http-equiv="REFRESH" content="0.2; URL=/meta-redirect-target/">
</head>
<body>
""")

MetaRedirectTarget = _html_resource("""
<html><body> META REDIRECT TARGET </body></html>
""")


class HttpRedirectResource(Resource):
    def render_GET(self, request):
        code = request.args['code'][0]
        url = '/getrequest?http_code=%s' % code
        request.setResponseCode(int(code))
        request.setHeader(b"location", url)
        request.finish()
        return NOT_DONE_YET


class CP1251Resource(Resource):
    def render_GET(self, request):
        request.setHeader("Content-Type", "text/html; charset=windows-1251")
        return u'''
                <html>
                <head>
                <meta http-equiv="Content-Type" content="text/html;charset=windows-1251">
                </head>
                <body>проверка</body>
                </html>
                '''.strip().encode('cp1251')


class InvalidContentTypeResource(Resource):
    def render_GET(self, request):
        request.setHeader("Content-Type", "ABRACADABRA: text/html; charset=windows-1251")
        return u'''проверка'''.encode('cp1251')


class Index(Resource):
    isLeaf = True

    def __init__(self, rootChildren):
        self.rootChildren = rootChildren

    def render(self, request):

        links = "\n".join([
            "<li><a href='%s'>%s</a></li>" % (path, path)
            for (path, child) in self.rootChildren.items() if path
        ])
        return """
        <html>
        <body><ul>%s</ul></body>
        </html>
        """ % links


class GzipRoot(Resource):
    def __init__(self, original_children):
        Resource.__init__(self)

        try:
            from twisted.web.server import GzipEncoderFactory
            from twisted.web.resource import EncodingResourceWrapper

            for path, child in original_children.items():
                self.putChild(
                    path,
                    EncodingResourceWrapper(child, [GzipEncoderFactory()])
                )
        except ImportError:
            pass


class Root(Resource):

    def __init__(self, http_port, https_port, proxy_port):
        Resource.__init__(self)
        self.log = []
        self.putChild("postrequest", PostResource())
        self.putChild("getrequest", GetResource())

        self.putChild("jsrender", JsRender())
        self.putChild("jsalert", JsAlert())
        self.putChild("jsconfirm", JsConfirm())
        self.putChild("jsinterval", JsInterval())
        self.putChild("jsviewport", JsViewport())
        self.putChild("tall", TallPage())
        self.putChild("baseurl", BaseUrl())
        self.putChild("delay", Delay())
        self.putChild("slow.gif", SlowImage())
        self.putChild("show-image", HtmlWithImage())
        self.putChild("iframes", IframeResource(http_port))
        self.putChild("externaliframe", ExternalIFrameResource(https_port=https_port))
        self.putChild("external", ExternalResource())
        self.putChild("cp1251", CP1251Resource())
        self.putChild("cp1251-invalid", InvalidContentTypeResource())
        self.putChild("bad-related", BadRelatedResource())

        self.putChild("jsredirect", JsRedirect())
        self.putChild("jsredirect-slowimage", JsRedirectSlowImage())
        self.putChild("jsredirect-onload", JsRedirectOnload())
        self.putChild("jsredirect-timer", JsRedirectTimer())
        self.putChild("jsredirect-chain", JsRedirectToJsRedirect())
        self.putChild("jsredirect-target", JsRedirectTarget())
        self.putChild("jsredirect-infinite", JsRedirectInfinite())
        self.putChild("jsredirect-infinite2", JsRedirectInfinite2())
        self.putChild("jsredirect-non-existing", JsRedirectToNonExisting())

        self.putChild("meta-redirect0", MetaRedirect0())
        self.putChild("meta-redirect-slowload", MetaRedirectSlowLoad())
        self.putChild("meta-redirect-slowload2", MetaRedirectSlowLoad2())
        self.putChild("meta-redirect1", MetaRedirect1())
        self.putChild("meta-redirect-target", MetaRedirectTarget())
        self.putChild("http-redirect", HttpRedirectResource())

        self.putChild("", Index(self.children))

        self.putChild("gzip", GzipRoot(self.children))


def cert_path():
    return os.path.join(os.path.dirname(__file__), "server.pem")

def ssl_factory():
    pem = cert_path()
    return ssl.DefaultOpenSSLContextFactory(pem, pem)


class ProxyClient(proxy.ProxyClient):
    def handleResponsePart(self, buffer):
        buffer = buffer.replace('</body>', ' PROXY_USED</body>')
        proxy.ProxyClient.handleResponsePart(self, buffer)

class ProxyClientFactory(proxy.ProxyClientFactory):
    protocol = ProxyClient

class ProxyRequest(proxy.ProxyRequest):
    protocols = {'http': ProxyClientFactory}

class Proxy(proxy.Proxy):
    requestFactory = ProxyRequest

class ProxyFactory(http.HTTPFactory):
    protocol = Proxy


def run(port_num, sslport_num, proxyport_num, verbose=True):
    root = Root(port_num, sslport_num, proxyport_num)
    factory = Site(root)
    port = reactor.listenTCP(port_num, factory)
    sslport = reactor.listenSSL(sslport_num, factory, ssl_factory())
    proxyport = reactor.listenTCP(proxyport_num, ProxyFactory())

    def print_listening():
        h = port.getHost()
        s = sslport.getHost()
        p = proxyport.getHost()
        print "Mock server running at http://%s:%d (http), https://%s:%d (https) and http://%s:%d (proxy)" % \
            (h.host, h.port, s.host, s.port, p.host, p.port)

    if verbose:
        import sys
        from twisted.python import log
        log.startLogging(sys.stdout)
        reactor.callWhenRunning(print_listening)

    reactor.run()


if __name__ == "__main__":
    op = optparse.OptionParser()
    op.add_option("--http-port", type=int, default=8998)
    op.add_option("--https-port", type=int, default=8999)
    op.add_option("--proxy-port", type=int, default=8990)
    op.add_option("-q", "--quiet", action="store_true", dest="quiet", default=False)
    opts, _ = op.parse_args()

    run(opts.http_port, opts.https_port, opts.proxy_port, not opts.quiet)

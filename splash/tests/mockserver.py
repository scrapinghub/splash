#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function
import os
import optparse
import base64
import random

from six.moves.urllib.parse import unquote

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
            value = type(value.decode('utf-8'))
        return value
    elif default is _REQUIRED:
        raise Exception("Missing argument: %s" % name)
    else:
        return default


def _html_resource(html):

    class HtmlResource(Resource):
        isLeaf = True
        template = html

        def __init__(self, http_port=None, https_port=None):
            Resource.__init__(self)
            self.http_port = http_port
            self.https_port = https_port

        def render(self, request):
            response = self.template % dict(
                http_port=self.http_port,
                https_port=self.https_port
            )
            # Twisted wants response to be bytes
            return response.encode('utf-8')

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

RedGreenPage = _html_resource("""
<html>
  <style type="text/css" media="screen">
    * { padding: 0px; margin: 0px }
    #left { float:left; width: 50%%; height: 100%%; background-color: #ff0000 }
    #right { float:left; width: 50%%; height: 100%%; background-color: #00ff00 }
  </style>
<body>
  <div id="left">&nbsp;</div><div id="right">&nbsp;</div>
</body>
</html>
""")

BadRelatedResource = _html_resource("""
<html>
<body>
<img src="http://non-existing">
</body>
</html>
""")


EggSpamScript = _html_resource("function egg(){return 'spam';}")


class BaseUrl(Resource):

    def render_GET(self, request):
        return b"""
<html>
<body>
<p id="p1">Before</p>
<script src="script.js"></script>
</body>
</html>
"""

    def getChild(self, name, request):
        if name == b"script.js":
            return self.ScriptJs()
        return self


    class ScriptJs(Resource):

        isLeaf = True

        def render_GET(self, request):
            request.setHeader(b"Content-Type", b"application/javascript")
            return b'document.getElementById("p1").innerHTML="After";'


class SetCookie(Resource):
    """
    Set a cookie with key=key and value=value.
    If "next" GET argument is passed, do a JS redirect to this "next" URL.
    """
    isLeaf = True

    def render_GET(self, request):
        key = getarg(request, b"key")
        value = getarg(request, b"value")
        next_url = unquote(getarg(request, b"next", ""))
        request.addCookie(key, value)
        if next_url:
            return (u"""
            <html><body>
            Redirecting now..
            <script> window.location = '%s'; </script>
            </body></html>
            """ % next_url).encode('utf-8')
        else:
            return "ok"


class GetCookie(Resource):
    """ Return a cookie with key=key """
    isLeaf = False
    def render_GET(self, request):
        value = request.getCookie(getarg(request, b"key").encode('utf-8')) or b""
        return value


class Delay(Resource):
    """ Accept the connection; write the response after ``n`` seconds. """
    isLeaf = True

    def render_GET(self, request):
        n = getarg(request, "n", 1, type=float)
        d = deferLater(reactor, n, lambda: (request, n))
        d.addCallback(self._delayedRender)
        return NOT_DONE_YET

    def _delayedRender(self, request_info):
        request, n = request_info
        request.write(("Response delayed for %0.3f seconds\n" % n).encode('utf-8'))
        if not request._disconnected:
            request.finish()


class SlowGif(Resource):
    """ 1x1 black gif that loads n seconds """

    isLeaf = True

    def render_GET(self, request):
        request.setHeader(b"Content-Type", b"image/gif")
        request.write(b"GIF89a")
        n = getarg(request, "n", 1, type=float)
        d = deferLater(reactor, n, lambda: (request, n))
        d.addCallback(self._delayedRender)
        return NOT_DONE_YET

    def _delayedRender(self, request_info):
        request, n = request_info
        # write 1px black gif
        gif_data = b'AQABAIAAAAAAAAAAACH5BAAAAAAALAAAAAABAAEAAAICTAEAOw=='
        request.write(base64.decodestring(gif_data))
        if not request._disconnected:
            request.finish()


class ShowImage(Resource):
    isLeaf = True

    def render_GET(self, request):
        token = random.random()  # prevent caching
        n = getarg(request, "n", 0, type=float)
        return ("""<html><body>
        <img id='foo' width=50 heigth=50 src="/slow.gif?n=%s&rnd=%s">
        </body></html>
        """ % (n, token)).encode('utf-8')


class IframeResource(Resource):

    def __init__(self, http_port):
        Resource.__init__(self)
        self.putChild(b"1.html", self.IframeContent1())
        self.putChild(b"2.html", self.IframeContent2())
        self.putChild(b"3.html", self.IframeContent3())
        self.putChild(b"4.html", self.IframeContent4())
        self.putChild(b"5.html", self.IframeContent5())
        self.putChild(b"6.html", self.IframeContent6())
        self.putChild(b"script.js", self.ScriptJs())
        self.putChild(b"script2.js", self.OtherDomainScript())
        self.putChild(b"nested.html", self.NestedIframeContent())
        self.http_port = http_port

    def render(self, request):
        return ("""
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
""" % self.http_port).encode('utf-8')

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
            request.setHeader(b"Content-Type", b"application/javascript")
            iframe_html = " SAME_DOMAIN <iframe src='/iframes/6.html'>js iframe created by document.write in external script doesn't work</iframe>"
            return ('''document.write("%s");''' % iframe_html).encode('utf-8')

    class OtherDomainScript(Resource):
        isLeaf = True
        def render(self, request):
            request.setHeader(b"Content-Type", b"application/javascript")
            return "document.write(' OTHER_DOMAIN ');".encode('utf-8')


class PostResource(Resource):
    """ Return a HTML file with all HTTP headers and the POST data """

    def render_POST(self, request):
        code = request.args.get('code', [200])[0]
        request.setResponseCode(int(code))
        headers = request.getAllHeaders()
        payload = request.content.getvalue() if request.content is not None else b''
        return ("""
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
""" % (headers, payload)).encode('utf-8')


class GetResource(Resource):
    """ Return a HTML file with all HTTP headers and all GET arguments """

    def render_GET(self, request):
        code = request.args.get(b'code', [200])[0]
        request.setResponseCode(int(code))
        empty_body = bool(request.args.get(b'empty', [b''])[0])
        if empty_body:
            return b""
        headers = request.getAllHeaders()
        payload = request.args
        return ("""
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
""" % (headers, payload)).encode('utf-8')


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


VeryLongGreenPage = _html_resource("""
<html>
<style>
* { margin: 0px; padding: 0px }
</style>
<body style="border: 1px solid #00FF77; height:59998px; background-color: #00FF77">
Hello, I am a loooooong green page
</body></html>
""")


RgbStripesPage = _html_resource("""
<html>
  <style>
    * { margin: 0px; padding: 0px; }
    body {
        background: -webkit-repeating-linear-gradient(
            -90deg,
            #ff0000, #ff0000 1px,
            #00ff00 1px, #00ff00 2px,
            #0000ff 2px, #0000ff 3px);
    width: 10px; height: 10px}
  </style>
  <body>
    &nbsp
  </body>
</html>
""")


class HttpRedirectResource(Resource):
    def render_GET(self, request):
        code = request.args[b'code'][0].decode('utf-8')
        url = '/getrequest?http_code=%s' % code
        request.setResponseCode(int(code))
        request.setHeader(b"location", url.encode('utf-8'))
        return ("%s redirect to %s" % (code, url)).encode('utf-8')


class JsRedirectTo(Resource):
    """ Do a JS redirect to an URL passed in "url" GET argument. """
    isLeaf = True

    def render_GET(self, request):
        url = getarg(request, b"url")
        next_url = unquote(url)
        return ("""
        <html><body>
        Redirecting now..
        <script> window.location = '%s'; </script>
        </body></html>
        """ % next_url).encode('utf-8')


class CP1251Resource(Resource):
    def render_GET(self, request):
        request.setHeader(b"Content-Type", b"text/html; charset=windows-1251")
        return u'''
                <html>
                <head>
                <meta http-equiv="Content-Type" content="text/html;charset=windows-1251">
                </head>
                <body>проверка</body>
                </html>
                '''.strip().encode('cp1251')


class Subresources(Resource):
    """ Embedded css and image """
    def render_GET(self, request):
        return ("""<html><head>
                <link rel="stylesheet" href="style.css?_rnd={0}" />
            </head>
            <body>
            <img id="image" src="img.gif?_rnd={0}"
                 onload="window.imageLoaded = true;"
                 onerror="window.imageLoaded = false;"/>
            </body>
        </html>""".format(random.randint(0, 1<<31))).encode('utf-8')

    def getChild(self, name, request):
        if name == b"style.css":
            return self.StyleSheet()
        if name == b"img.gif":
            return self.Image()
        return self

    class StyleSheet(Resource):
        def render_GET(self, request):
            request.setHeader(b"Content-Type", b"text/css; charset=utf-8")
            print("Request Style!")
            return b"body { background-color: red; }"
    class Image(Resource):
        def render_GET(self, request):
            request.setHeader(b"Content-Type", b"image/gif")
            return base64.decodestring(b'R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=')


class SetHeadersResource(Resource):
    def render_GET(self, request):
        for k, values in request.args.items():
            for v in values:
                request.setHeader(k, v)
        return b""

class InvalidContentTypeResource(Resource):
    def render_GET(self, request):
        request.setHeader(b"Content-Type", b"ABRACADABRA: text/html; charset=windows-1251")
        return u'''проверка'''.encode('cp1251')


class InvalidContentTypeResource2(Resource):
    def render_GET(self, request):
        request.setHeader(b"Content-Type", b"text-html; charset=utf-8")
        return b"ok"


class Index(Resource):
    isLeaf = True

    def __init__(self, rootChildren):
        self.rootChildren = rootChildren

    def render(self, request):

        links = "\n".join([
            "<li><a href='%s'>%s</a></li>" % (path, path)
            for (path, child) in self.rootChildren.items() if path
        ])
        return ("""
        <html>
        <body><ul>%s</ul></body>
        </html>
        """ % links).encode('utf-8')


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

        self.putChild(b"postrequest", PostResource())
        self.putChild(b"getrequest", GetResource())

        self.putChild(b"jsrender", JsRender())
        self.putChild(b"jsalert", JsAlert())
        self.putChild(b"jsconfirm", JsConfirm())
        self.putChild(b"jsinterval", JsInterval())
        self.putChild(b"jsviewport", JsViewport())
        self.putChild(b"tall", TallPage())
        self.putChild(b"red-green", RedGreenPage())
        self.putChild(b"baseurl", BaseUrl())
        self.putChild(b"delay", Delay())
        self.putChild(b"slow.gif", SlowGif())
        self.putChild(b"show-image", ShowImage())
        self.putChild(b"iframes", IframeResource(http_port))
        self.putChild(b"externaliframe", ExternalIFrameResource(https_port=https_port))
        self.putChild(b"external", ExternalResource())
        self.putChild(b"cp1251", CP1251Resource())
        self.putChild(b"cp1251-invalid", InvalidContentTypeResource())
        self.putChild(b"bad-related", BadRelatedResource())
        self.putChild(b"set-cookie", SetCookie()),
        self.putChild(b"get-cookie", GetCookie()),
        self.putChild(b"eggspam.js", EggSpamScript()),
        self.putChild(b"very-long-green-page", VeryLongGreenPage())
        self.putChild(b"rgb-stripes", RgbStripesPage())
        self.putChild(b"subresources", Subresources())
        self.putChild(b"set-header", SetHeadersResource())

        self.putChild(b"jsredirect", JsRedirect())
        self.putChild(b"jsredirect-to", JsRedirectTo())
        self.putChild(b"jsredirect-slowimage", JsRedirectSlowImage())
        self.putChild(b"jsredirect-onload", JsRedirectOnload())
        self.putChild(b"jsredirect-timer", JsRedirectTimer())
        self.putChild(b"jsredirect-chain", JsRedirectToJsRedirect())
        self.putChild(b"jsredirect-target", JsRedirectTarget())
        self.putChild(b"jsredirect-infinite", JsRedirectInfinite())
        self.putChild(b"jsredirect-infinite2", JsRedirectInfinite2())
        self.putChild(b"jsredirect-non-existing", JsRedirectToNonExisting())

        self.putChild(b"meta-redirect0", MetaRedirect0())
        self.putChild(b"meta-redirect-slowload", MetaRedirectSlowLoad())
        self.putChild(b"meta-redirect-slowload2", MetaRedirectSlowLoad2())
        self.putChild(b"meta-redirect1", MetaRedirect1())
        self.putChild(b"meta-redirect-target", MetaRedirectTarget())
        self.putChild(b"http-redirect", HttpRedirectResource())

        self.putChild(b"", Index(self.children))

        self.putChild(b"gzip", GzipRoot(self.children))


def cert_path():
    return os.path.join(os.path.dirname(__file__), "server.pem")

def ssl_factory():
    pem = cert_path()
    return ssl.DefaultOpenSSLContextFactory(pem, pem)


class ProxyClient(proxy.ProxyClient):
    def handleResponsePart(self, buffer):
        buffer = buffer.replace(b'</body>', b' PROXY_USED</body>')
        proxy.ProxyClient.handleResponsePart(self, buffer)

class ProxyClientFactory(proxy.ProxyClientFactory):
    protocol = ProxyClient

class ProxyRequest(proxy.ProxyRequest):
    protocols = {b'http': ProxyClientFactory}

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
        print("Mock server running at http://%s:%d (http), https://%s:%d (https) and http://%s:%d (proxy)" %
              (h.host, h.port, s.host, s.port, p.host, p.port))

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

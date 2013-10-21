from twisted.web import http
from twisted.web import resource
from twisted.web.error import UnsupportedMethod
from twisted.python.compat import intToBytes
from twisted.python import log, _reflectpy3 as reflect, failure
from resources import RenderHtml, RenderPng, RenderJson


NOT_DONE_YET = 1
SPLASH_HEADER_PREFIX = 'X-Splash-'
SPLASH_RENDERS = {'html': RenderHtml,
                  'png': RenderPng,
                  'json': RenderJson,
                  }
HTML_PARAMS = ['baseurl', 'timeout', 'wait', 'proxy', 'allowed_domains', 'viewport', 'js']
PNG_PARAMS = ['width', 'height']
JSON_PARAMS = ['html', 'png', 'iframes', 'script', 'console']


class SplashProxyRequest(http.Request):

    def __init__(self, channel, queued):
        http.Request.__init__(self, channel, queued)
        self.pool = channel.pool


    def _get_header(self, name):
        return self.getHeader(SPLASH_HEADER_PREFIX + name)


    def _set_header_as_params(self, param_list):
        for parameter in param_list:
            value = self._get_header(parameter)
            if value is not None:
                self.args[parameter] = [value]


    def process(self):
        try:
            # load render class
            render_name = self._get_header('render')
            rendercls = SPLASH_RENDERS.get(render_name)
            if rendercls is None:
                self.invalidParameters('render')
                return

            # setup request parameters
            self.args['url'] = [self.uri]
            self._set_header_as_params(HTML_PARAMS)

            if render_name == 'png':
                self._set_header_as_params(PNG_PARAMS)
            elif render_name == 'json':
                self._set_header_as_params(JSON_PARAMS)

            render = rendercls(self.pool)
            self.render(render)
        except:
            self.processingFailed(failure.Failure())


    def render(self, resrc):
        try:
            body = resrc.render(self)
        except UnsupportedMethod as e:
            epage = resource.ErrorPage(http.NOT_ALLOWED, "Method Not Allowed")
            body = epage.render(self)

        if body == NOT_DONE_YET:
            return
        if not isinstance(body, bytes):
            body = resource.ErrorPage(
                http.INTERNAL_SERVER_ERROR,
                "Request did not return bytes",
                "Request: " + html.PRE(reflect.safe_repr(self)) + "<br />" +
                "Resource: " + html.PRE(reflect.safe_repr(resrc)) + "<br />" +
                "Value: " + html.PRE(reflect.safe_repr(body))).render(self)

        self.setHeader(b'content-length',
                       intToBytes(len(body)))
        self.write(body)
        self.finish()


    def processingFailed(self, reason):
        log.err(reason)
        body = (b"<html><head><title>Processing Failed</title></head><body>"
                b"<b>Processing Failed</b></body></html>")
        self.setResponseCode(http.INTERNAL_SERVER_ERROR)
        self.setHeader(b'content-type', b"text/html")
        self.setHeader(b'content-length', intToBytes(len(body)))
        self.write(body)
        self.finish()
        return reason


    def invalidParameters(self, name):
        reason = SPLASH_HEADER_PREFIX + '%s header is invalid or missing' % name
        log.err(reason)
        body = (b"<html><head><title>Bad Request/title></head><body>"
                b"<b>%s</b></body></html>" % reason)
        self.setResponseCode(http.BAD_REQUEST)
        self.setHeader(b'content-type', b"text/html")
        self.setHeader(b'content-length', intToBytes(len(body)))
        self.write(body)
        self.finish()
        return reason


class SplashProxy(http.HTTPChannel):

    requestFactory = SplashProxyRequest


class SplashProxyFactory(http.HTTPFactory):

    protocol = SplashProxy

    def __init__(self, pool, logPath=None, timeout=60 * 60 * 12):
        http.HTTPFactory.__init__(self, logPath=logPath, timeout=timeout)
        self.pool = pool

    def buildProtocol(self, addr):
        p = http.HTTPFactory.buildProtocol(self, addr)
        p.pool = self.pool
        return p

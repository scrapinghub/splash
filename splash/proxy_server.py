"""
Splash can act as an HTTP proxy server. When request is made through
the Splash Proxy an user gets a rendered DOM snapshot instead of a raw HTML.

Not to be confused with Splash support for proxying outgoing requests
(see :mod:`splash.proxy`).
"""
from __future__ import absolute_import
from twisted.web import http
from twisted.web.error import UnsupportedMethod
from twisted.python import failure
from splash.resources import (RenderHtmlResource, RenderPngResource,
                              RenderJpegResource, RenderJsonResource)

NOT_DONE_YET = 1
SPLASH_HEADER_PREFIX = 'x-splash-'
SPLASH_RESOURCES = {
    'html': RenderHtmlResource,
    'png': RenderPngResource,
    'jpeg': RenderJpegResource,
    'json': RenderJsonResource,
}

# Note the http header use '-' instead of '_' for the parameter names
HTML_PARAMS = ['baseurl', 'timeout', 'wait', 'proxy', 'allowed-domains',
               'viewport', 'js', 'js-source', 'images', 'filters',
               'render-all', 'scale-method', 'resource-timeout']
PNG_PARAMS = ['width', 'height']
JPEG_PARAMS = ['width', 'height', 'quality']
JSON_PARAMS = ['html', 'png', 'jpeg', 'iframes', 'script', 'console', 'history', 'har']

HOP_BY_HOP_HEADERS = [
    'Connection',
    'Keep-Alive',
    'Proxy-Authenticate',
    'Proxy-Authorization',
    'TE',
    'Trailer',
    'Transfer-Encoding',
    'Upgrade',
]


class SplashProxyRequest(http.Request):
    inspect_me = True

    def __init__(self, channel, queued):
        http.Request.__init__(self, channel, queued)
        self.pool = channel.pool
        self.max_timeout = channel.max_timeout

    def _get_header(self, name):
        return self.getHeader(SPLASH_HEADER_PREFIX + name)

    def _fill_args_from_headers(self, arg_names):
        for parameter in arg_names:
            value = self._get_header(parameter)
            if value is not None:
                # normal splash parameter use underscore instead of dash
                parameter = parameter.replace('-', '_')
                self.args[parameter] = [value]

    def _remove_splash_headers(self):
        headers = self.getAllHeaders()
        for name, value in headers.items():
            if SPLASH_HEADER_PREFIX in name.lower():
                self.requestHeaders.removeHeader(name)

    def _remove_host_header(self):
        # According to RFC2616 Section 5.1.2 clients MUST send
        # Request-URI as absoluteURI when working with a proxy
        # (see http://tools.ietf.org/html/rfc2616#section-5.1.2).
        # And according to the same RFC Section 5.2
        # (see http://tools.ietf.org/html/rfc2616#section-5.2),
        # any Host header field value in the request MUST be
        # ignored if an absolute URI is used - that's what we're
        # doing here.
        self.requestHeaders.removeHeader('Host')

    def _remove_hop_by_hop_headers(self):
        # See http://tools.ietf.org/html/draft-ietf-httpbis-p1-messaging-14#section-7.1.3.1
        connection = self.requestHeaders.getRawHeaders('Connection', [])
        for value in connection:
            for name in value.split(','):
                self.requestHeaders.removeHeader(name.strip())

        for name in HOP_BY_HOP_HEADERS:
            self.requestHeaders.removeHeader(name)

    def _remove_accept_encoding_header(self):
        # Splash renders the contents and returns a snapshot of the
        # rendered DOM. The data is rendered using QWebKit, and it is
        # QWebKit who knows which content encodings it can handle.
        # That's why the original Accept-Encoding header is not passed
        # to the remote server when Splash works as a proxy server.

        # Another reason is https://bugs.webkit.org/show_bug.cgi?id=63696.
        # Passing custom Accept-Encoding header disables automatic
        # gzip decompression in WebKit and thus makes Splash return raw gzip
        # data instead of the rendered HTML page - we don't want this.

        # XXX: Should we respect Accept-Encoding by returning
        # *rendered* data properly compressed? Or maybe users should put
        # another proxy (e.g. nginx) in front of Splash to handle this?
        self.requestHeaders.removeHeader('Accept-Encoding')

    def process(self):
        try:
            # load resource class
            resource_name = self._get_header('render')
            resource_cls = SPLASH_RESOURCES.get(resource_name)
            if resource_cls is None:
                self.invalidParameter('render')
                return

            # setup request parameters
            self.args['url'] = [self.uri]
            self._fill_args_from_headers(HTML_PARAMS)

            if resource_name == 'png':
                self._fill_args_from_headers(PNG_PARAMS)
            elif resource_name == 'jpeg':
                self._fill_args_from_headers(JPEG_PARAMS)
            elif resource_name == 'json':
                self._fill_args_from_headers(JPEG_PARAMS)
                self._fill_args_from_headers(JSON_PARAMS)

            # make sure no splash headers are sent to the target
            self._remove_splash_headers()

            # remove some other headers to be a good proxy
            self._remove_host_header()
            self._remove_hop_by_hop_headers()
            self._remove_accept_encoding_header()

            resource = resource_cls(self.pool, max_timeout=self.max_timeout, is_proxy_request=True)
            self.render(resource)

        except Exception as e:
            print e
            self.processingFailed(failure.Failure())

    def render(self, resource):
        try:
            body = resource.render(self)
        except UnsupportedMethod:
            return self.methodNotAllowed()

        if body == NOT_DONE_YET:
            return

        # errors handled by resources don't return a body, they write
        # to the request directly.
        if body:
            self.setHeader('content-length', str(len(body)))
            self.write(body)
        self.finish()

    def processingFailed(self, reason):
        self.setResponseCode(500)
        self.write('Error handling request')
        self.finish()

    def methodNotAllowed(self):
        self.setResponseCode(405)
        self.write('Method Not Allowed')
        self.finish()

    def invalidParameter(self, name):
        self.setResponseCode(400)
        self.write('%s header is invalid or missing' % (SPLASH_HEADER_PREFIX + name))
        self.finish()


class SplashProxy(http.HTTPChannel):
    requestFactory = SplashProxyRequest


class SplashProxyServerFactory(http.HTTPFactory):
    protocol = SplashProxy

    def __init__(self, pool, max_timeout, logPath=None, timeout=60 * 60 * 12):
        http.HTTPFactory.__init__(self, logPath=logPath, timeout=timeout)
        self.pool = pool
        self.max_timeout = max_timeout

    def buildProtocol(self, addr):
        p = http.HTTPFactory.buildProtocol(self, addr)
        p.pool = self.pool
        p.max_timeout = self.max_timeout
        return p

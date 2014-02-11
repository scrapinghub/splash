from twisted.web import http
from twisted.web.error import UnsupportedMethod
from twisted.python import log, failure
from resources import RenderHtml, RenderPng, RenderJson


NOT_DONE_YET = 1
SPLASH_HEADER_PREFIX = 'x-splash-'
SPLASH_RESOURCES = {'html': RenderHtml,
                    'png': RenderPng,
                    'json': RenderJson,
                    }

# Note the http header use '-' instead of '_' for the parameter names
HTML_PARAMS = ['baseurl', 'timeout', 'wait', 'proxy', 'allowed-domains',
               'viewport', 'js', 'js-source']
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
                # normal splash parameter use underscore instead of dash
                parameter = parameter.replace('-', '_')
                self.args[parameter] = [value]

    def _remove_splash_headers(self):
        headers = self.getAllHeaders()
        for header_name, header_value in headers.items():
            if SPLASH_HEADER_PREFIX in header_name.lower():
                self.requestHeaders.removeHeader(header_name)

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
            self._set_header_as_params(HTML_PARAMS)

            if resource_name == 'png':
                self._set_header_as_params(PNG_PARAMS)
            elif resource_name == 'json':
                self._set_header_as_params(PNG_PARAMS)
                self._set_header_as_params(JSON_PARAMS)

            # make sure no splash headers are sent to the target
            self._remove_splash_headers()

            resource = resource_cls(self.pool, True)
            self.render(resource)

        except Exception, e:
            print e
            self.processingFailed(failure.Failure())

    def render(self, resource):
        try:
            body = resource.render(self)
        except UnsupportedMethod as e:
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


class SplashProxyFactory(http.HTTPFactory):

    protocol = SplashProxy

    def __init__(self, pool, logPath=None, timeout=60 * 60 * 12):
        http.HTTPFactory.__init__(self, logPath=logPath, timeout=timeout)
        self.pool = pool

    def buildProtocol(self, addr):
        p = http.HTTPFactory.buildProtocol(self, addr)
        p.pool = self.pool
        return p

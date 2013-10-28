import unittest, requests, json, base64, urllib, urlparse
from cStringIO import StringIO
from PIL import Image
from splash import defaults
from splash.tests import ts, test_render


SPLASH_HEADER_PREFIX = 'X-Splash-'


class ProxyRequestHandler:

    render_format = "html"

    @property
    def proxies(self):
        return {'http': 'localhost:%d' % ts.splashserver.proxy_portnum}

    def _get_val(self, v):
        if isinstance(v, list):
            return v[0]
        else:
            return v

    def _get_header(self, name):
        return SPLASH_HEADER_PREFIX + name

    def request(self, query, render_format=None):
        render_format = render_format or self.render_format

        headers = {self._get_header('render'):render_format}
        if not isinstance(query, dict):
            query = urlparse.parse_qs(query)

        url = self._get_val(query.get('url'))
        for k, v in query.items():
            if k != 'url':
                headers[self._get_header(k)] = self._get_val(v)

        return requests.get(url, headers=headers, proxies=self.proxies)

    def post(self, query, render_format=None, payload=None, headers=None):
        raise NotImplementedError


class ProxyRenderHtmlTest(test_render.RenderHtmlTest):

    request_handler = ProxyRequestHandler

    def test_missing_url(self):
        # doesn't make sense to test when using splash as a proxy
        pass

    def test_ok_https(self):
        # no proxy https support
        pass


class ProxyRenderPngTest(test_render.RenderPngTest):

    request_handler = ProxyRequestHandler

    def test_missing_url(self):
        # doesn't make sense to test when using splash as a proxy
        pass

    def test_ok_https(self):
        # no proxy https support
        pass


class ProxyRenderJsonTest(test_render.RenderJsonTest):

    request_handler = ProxyRequestHandler

    def test_missing_url(self):
        # doesn't make sense to test when using splash as a proxy
        pass

    def test_jsrender_https_html(self):
        # no proxy https support
        pass

    def test_jsrender_https_png(self):
        # no proxy https support
        pass

    def test_fields_all(self):
        # no proxy https support
        pass

    def test_fields_no_html(self):
        # no proxy https support
        pass

    def test_fields_no_screenshots(self):
        # no proxy https support
        pass

    def test_fields_no_iframes(self):
        # no proxy https support
        pass

    def test_fields_default(self):
        # no proxy https support
        pass


class ProxyRunJsTest(test_render.RunJsTest):

    request_handler = ProxyRequestHandler

    def test_js_incorrect_content_type(self):
        # check not done by the proxy.
        pass

    def _runjs_request(self, js_source, render_format=None, params=None, headers=None):
        query = {'url': 'http://localhost:8998/jsrender',
                 'js_source': js_source,
                 'script': 1}
        query.update(params or {})
        return self.request(query, render_format=render_format)

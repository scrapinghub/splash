import unittest, requests, json, base64, urllib, urlparse, simplejson
from cStringIO import StringIO
from PIL import Image
from splash import defaults
from splash.tests import ts, test_render


SPLASH_HEADER_PREFIX = 'x-splash-'


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
        return SPLASH_HEADER_PREFIX + name.replace('_', '-')

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
        render_format = render_format or self.render_format
        headers = headers if headers is not None else {}
        headers[self._get_header('render')] = render_format
        if not isinstance(query, dict):
            query = urlparse.parse_qs(query)

        url = self._get_val(query.get('url'))
        for k, v in query.items():
            if k != 'url':
                headers[self._get_header(k)] = self._get_val(v)

        return requests.post(url, data=payload, headers=headers,
                             proxies=self.proxies)


class ProxyRenderHtmlTest(test_render.RenderHtmlTest):

    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True


class ProxyRenderPngTest(test_render.RenderPngTest):

    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True


class ProxyRenderJsonTest(test_render.RenderJsonTest):

    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True


class ProxyRunJsTest(test_render.RunJsTest):

    request_handler = ProxyRequestHandler
    proxy_test = True

    def _runjs_request(self, js_source, render_format=None, params=None, headers=None):
        query = {'url': 'http://localhost:8998/jsrender',
                 'js_source': js_source,
                 'script': 1}
        query.update(params or {})
        return self.request(query, render_format=render_format)


class ProxyPostTest(test_render._BaseRenderTest):

    request_handler = ProxyRequestHandler

    def test_post_request(self):
        r = self.post("url=http://localhost:8998/postrequest")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("From POST" in r.text)

    def test_post_headers(self):
        headers = {'X-Custom-Header1': 'some-val1',
                   'X-Custom-Header2': 'some-val2',
                   }
        r = self.post("url=http://localhost:8998/postrequest", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("'x-custom-header1': 'some-val1'" in r.text)
        self.assertTrue("'x-custom-header2': 'some-val2'" in r.text)
        self.assertTrue("x-splash" not in r.text)

    def test_post_payload(self):
        # simply post body
        payload = {'some': 'data'}
        json_payload = simplejson.dumps(payload)
        r = self.post("url=http://localhost:8998/postrequest", payload=json_payload)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(json_payload in r.text)

        # form encoded fields
        payload = {'form_field1': 'value1',
                   'form_field2': 'value2', }
        r = self.post("url=http://localhost:8998/postrequest", payload=payload)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('form_field2=value2&amp;form_field1=value1' in r.text)

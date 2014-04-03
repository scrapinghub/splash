import unittest, requests, json, base64, urllib, urlparse, json
from cStringIO import StringIO
from PIL import Image
from splash import defaults
from splash.tests import ts, test_render


SPLASH_HEADER_PREFIX = 'x-splash-'


class ProxyRequestHandler(object):

    render_format = "html"

    @property
    def proxies(self):
        return {'http': 'http://localhost:%d' % ts.splashserver.proxy_portnum}

    def _get_val(self, v):
        if isinstance(v, list):
            return v[0]
        else:
            return v

    def _get_header(self, name):
        return SPLASH_HEADER_PREFIX + name.replace('_', '-')

    def request(self, query, render_format=None, headers=None):
        render_format = render_format or self.render_format

        _headers = {self._get_header('render'): render_format}
        _headers.update(headers or {})
        if not isinstance(query, dict):
            query = urlparse.parse_qs(query)

        url = self._get_val(query.get('url'))
        for k, v in query.items():
            if k != 'url':
                _headers[self._get_header(k)] = self._get_val(v)

        return requests.get(url, headers=_headers, proxies=self.proxies)

    def post(self, query, render_format=None, payload=None, headers=None):
        render_format = render_format or self.render_format

        _headers = {self._get_header('render'): render_format}
        _headers.update(headers or {})

        if not isinstance(query, dict):
            query = urlparse.parse_qs(query)

        url = self._get_val(query.get('url'))
        for k, v in query.items():
            if k != 'url':
                _headers[self._get_header(k)] = self._get_val(v)

        return requests.post(url, data=payload, headers=_headers,
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
        query = {'url': ts.mockserver.url("jsrender"),
                 'js_source': js_source,
                 'script': 1}
        query.update(params or {})
        return self.request(query, render_format=render_format)


class ProxyPostTest(test_render.BaseRenderTest):

    request_handler = ProxyRequestHandler

    def test_post_request(self):
        r = self.post({"url": ts.mockserver.url("postrequest")})
        self.assertEqual(r.status_code, 200)
        self.assertTrue("From POST" in r.text)

    def test_post_headers(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
        }
        r = self.post({"url": ts.mockserver.url("postrequest")}, headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIn("'x-custom-header1': 'some-val1'", r.text)
        self.assertIn("'custom-header2': 'some-val2'", r.text)
        self.assertNotIn("x-splash", r.text.lower())

    # unittest.expectedFailure doesn't work with nose
    @unittest.skipIf(True, "expected failure")
    def test_post_request_baseurl(self):
        r = self.post({
            "url": ts.mockserver.url("postrequest"),
            "baseurl": ts.mockserver.url("postrequest"),
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue("From POST" in r.text)

    # unittest.expectedFailure doesn't work with nose
    @unittest.skipIf(True, "expected failure")
    def test_post_headers_baseurl(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
        }
        r = self.post({
                "url": ts.mockserver.url("postrequest"),
                "baseurl": ts.mockserver.url("postrequest")
            },
            headers=headers
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("'x-custom-header1': 'some-val1'", r.text)
        self.assertIn("'custom-header2': 'some-val2'", r.text)
        self.assertNotIn("x-splash", r.text.lower())

    def test_post_user_agent(self):
        r = self.post({"url": ts.mockserver.url("postrequest")}, headers={
            'User-Agent': 'Mozilla',
        })
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("x-splash", r.text.lower())
        self.assertIn("'user-agent': 'Mozilla'", r.text)

    def test_post_payload(self):
        # simply post body
        payload = {'some': 'data'}
        json_payload = json.dumps(payload)
        r = self.post({"url": ts.mockserver.url("postrequest")}, payload=json_payload)
        self.assertEqual(r.status_code, 200)
        self.assertIn(json_payload, r.text)

        # form encoded fields
        payload = {'form_field1': 'value1',
                   'form_field2': 'value2', }
        r = self.post({"url": ts.mockserver.url("postrequest")}, payload=payload)
        self.assertEqual(r.status_code, 200)
        self.assertIn('form_field2=value2&amp;form_field1=value1', r.text)


class ProxyGetTest(test_render.BaseRenderTest):
    request_handler = ProxyRequestHandler

    def test_get_headers(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
            'User-Agent': 'Mozilla',
        }
        r = self.request({"url": ts.mockserver.url("getrequest")}, headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIn("'x-custom-header1': 'some-val1'", r.text)
        self.assertIn("'custom-header2': 'some-val2'", r.text)
        self.assertIn("'user-agent': 'Mozilla'", r.text)
        self.assertNotIn("x-splash", r.text)


class NoProxyGetTest(test_render.BaseRenderTest):

    def test_get_headers(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
            'User-Agent': 'Mozilla',
        }
        r = self.request({"url": ts.mockserver.url("getrequest")}, headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("'x-custom-header1': 'some-val1'", r.text)
        self.assertNotIn("'custom-header2': 'some-val2'", r.text)
        self.assertNotIn("'user-agent': 'Mozilla'", r.text)
        self.assertNotIn("x-splash", r.text)


class NoProxyPostTest(test_render.BaseRenderTest):

    def test_post_headers(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
            'Content-Type': 'application/javascript', # required by non-proxy POSTs
        }
        r = self.post({"url": ts.mockserver.url("postrequest")}, headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("'x-custom-header1': 'some-val1'", r.text)
        self.assertNotIn("'custom-header2': 'some-val2'", r.text)
        self.assertNotIn("x-splash", r.text.lower())

    def test_post_user_agent(self):
        r = self.post({"url": ts.mockserver.url("postrequest")}, headers={
            'User-Agent': 'Mozilla',
            'Content-Type': 'application/javascript',  # required by non-proxy POSTs
        })
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("x-splash", r.text.lower())
        self.assertNotIn("'user-agent': 'Mozilla'", r.text)


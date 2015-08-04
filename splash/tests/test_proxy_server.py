import urlparse
import json

import requests
import pytest

from splash.tests import test_render, test_redirects, test_request_filters


SPLASH_HEADER_PREFIX = 'x-splash-'


class ProxyRequestHandler(object):

    endpoint = "render.html"

    def __init__(self, ts):
        self.ts = ts

    @property
    def proxies(self):
        return {'http': self.ts.splashserver.proxy_url()}

    def request(self, query, endpoint=None, headers=None, proxies=None):
        url, headers = self._request_params(query, endpoint, headers)
        proxies = proxies if proxies is not None else self.proxies
        return requests.get(url, headers=headers, proxies=proxies)

    def post(self, query, endpoint=None, payload=None, headers=None, proxies=None):
        url, headers = self._request_params(query, endpoint, headers)
        proxies = proxies if proxies is not None else self.proxies
        return requests.post(url, data=payload, headers=headers, proxies=proxies)

    def _request_params(self, query, endpoint, headers):
        endpoint = endpoint or self.endpoint
        assert endpoint.startswith("render.")
        _headers = {self._get_header('render'): endpoint[len("render."):]}
        _headers.update(headers or {})
        if not isinstance(query, dict):
            query = urlparse.parse_qs(query)

        url = self._get_val(query.get('url'))
        for k, v in query.items():
            if k != 'url':
                _headers[self._get_header(k)] = self._get_val(v)

        return url, _headers

    def _get_val(self, v):
        if isinstance(v, list):
            return v[0]
        else:
            return v

    def _get_header(self, name):
        return SPLASH_HEADER_PREFIX + name.replace('_', '-')


class ProxyRenderHtmlTest(test_render.RenderHtmlTest):
    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True
    use_gzip = False


class GzipProxyRenderHtmlTest(ProxyRenderHtmlTest):
    use_gzip = True


class ProxyRenderPngTest(test_render.RenderPngTest):
    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True
    use_gzip = False


class ProxyRenderJpegTest(test_render.RenderJpegTest):
    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True
    use_gzip = False


class GzipProxyRenderPngTest(ProxyRenderPngTest):
    use_gzip = True


class ProxyRenderJsonTest(test_render.RenderJsonTest):
    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True
    use_gzip = False


class GzipProxyRenderJsonTest(ProxyRenderJsonTest):
    use_gzip = True


class ProxyRenderJsonHistoryTest(test_render.RenderJsonHistoryTest):
    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True
    use_gzip = False


class ProxyHttpRedirectTest(test_redirects.HttpRedirectTest):
    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True
    use_gzip = False


class GzipProxyHttpRedirectTest(ProxyHttpRedirectTest):
    use_gzip = True


class ProxyMetaRedirectTest(test_redirects.MetaRedirectTest):
    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True
    use_gzip = False


class GzipProxyMetaRedirectTest(ProxyMetaRedirectTest):
    use_gzip = True


class ProxyJsRedirectTest(test_redirects.JsRedirectTest):
    request_handler = ProxyRequestHandler
    https_supported = False
    proxy_test = True
    use_gzip = False


class GzipProxyJsRedirectTest(ProxyJsRedirectTest):
    use_gzip = True


#
# See https://github.com/scrapinghub/splash/issues/241.
# We'll have to change X-Splash-js-source interface to fix these tests.
#

# class ProxyRunJsTest(test_runjs.RunJsTest):
#
#     request_handler = ProxyRequestHandler
#     proxy_test = True
#     use_gzip = False
#
#     def _runjs_request(self, js_source, endpoint=None, params=None, headers=None):
#         query = {'url': self.mockurl("jsrender"),
#                  'js_source': js_source,
#                  'script': 1}
#         query.update(params or {})
#         return self.request(query, endpoint=endpoint)
#
#
# class GzipProxyRunJsTest(ProxyRunJsTest):
#     use_gzip = True


class ProxyPostTest(test_render.BaseRenderTest):

    request_handler = ProxyRequestHandler
    use_gzip = False

    def test_post_request(self):
        r = self.post({"url": self.mockurl("postrequest")})
        self.assertStatusCode(r, 200)
        self.assertTrue("From POST" in r.text)

    def test_post_headers(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
            'Custom-Header3': 'some-val3',
            'Connection': 'custom-Header3, Foo, Bar',
        }
        r = self.post({"url": self.mockurl("postrequest")}, headers=headers)
        self.assertStatusCode(r, 200)
        self.assertIn("'x-custom-header1': 'some-val1'", r.text)
        self.assertIn("'custom-header2': 'some-val2'", r.text)

        # X-Splash headers should be removed
        self.assertNotIn("x-splash", r.text.lower())

        # Connection header is handled correctly
        self.assertNotIn("custom-header3", r.text.lower())
        self.assertNotIn("foo", r.text.lower())
        self.assertNotIn("bar", r.text.lower())

    @pytest.mark.xfail
    def test_post_request_baseurl(self):
        r = self.post({
            "url": self.mockurl("postrequest"),
            "baseurl": self.mockurl("postrequest"),
        })
        self.assertStatusCode(r, 200)
        self.assertTrue("From POST" in r.text)

    @pytest.mark.xfail
    def test_post_headers_baseurl(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
        }
        r = self.post({
                "url": self.mockurl("postrequest"),
                "baseurl": self.mockurl("postrequest")
            },
            headers=headers
        )
        self.assertStatusCode(r, 200)
        self.assertIn("'x-custom-header1': 'some-val1'", r.text)
        self.assertIn("'custom-header2': 'some-val2'", r.text)
        self.assertNotIn("x-splash", r.text.lower())

    def test_post_user_agent(self):
        r = self.post({"url": self.mockurl("postrequest")}, headers={
            'User-Agent': 'Mozilla',
        })
        self.assertStatusCode(r, 200)
        self.assertNotIn("x-splash", r.text.lower())
        self.assertIn("'user-agent': 'Mozilla'", r.text)

    def test_post_payload(self):
        # simply post body
        payload = {'some': 'data'}
        json_payload = json.dumps(payload)
        r = self.post({"url": self.mockurl("postrequest")}, payload=json_payload)
        self.assertStatusCode(r, 200)
        self.assertIn(json_payload, r.text)

        # form encoded fields
        payload = {'form_field1': 'value1',
                   'form_field2': 'value2', }
        r = self.post({"url": self.mockurl("postrequest")}, payload=payload)
        self.assertStatusCode(r, 200)
        self.assertIn('form_field2=value2&amp;form_field1=value1', r.text)


class GzipProxyPostTest(ProxyPostTest):
    use_gzip = True


class ProxyGetTest(test_render.BaseRenderTest):
    request_handler = ProxyRequestHandler
    use_gzip = False

    def test_get_headers(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
            'Custom-Header3': 'some-val3',
            'User-Agent': 'Mozilla',
            'Connection': 'custom-Header3, Foo, Bar',
        }
        r = self.request({"url": self.mockurl("getrequest")}, headers=headers)
        self.assertStatusCode(r, 200)
        self.assertIn("'x-custom-header1': 'some-val1'", r.text)
        self.assertIn("'custom-header2': 'some-val2'", r.text)
        self.assertIn("'user-agent': 'Mozilla'", r.text)

        # X-Splash headers should be removed
        self.assertNotIn("x-splash", r.text.lower())

        # Connection header is handled correctly
        self.assertNotIn("custom-header3", r.text.lower())
        self.assertNotIn("foo", r.text.lower())
        self.assertNotIn("bar", r.text.lower())

    def test_get_user_agent(self):
        headers = {'User-Agent': 'Mozilla123'}
        r = self.request({"url": self.mockurl("getrequest")}, headers=headers)
        self.assertStatusCode(r, 200)
        self.assertIn("'user-agent': 'Mozilla123'", r.text)

    def test_connection_user_agent(self):
        headers = {
            'User-Agent': 'Mozilla123',
            'Connection': 'User-agent',
        }
        r = self.request({"url": self.mockurl("getrequest")}, headers=headers)
        self.assertStatusCode(r, 200)
        self.assertNotIn("'user-agent': 'Mozilla123'", r.text)
        self.assertNotIn("mozilla123", r.text.lower())


class GzipProxyGetTest(ProxyGetTest):
    use_gzip = True


class NoProxyGetTest(test_render.BaseRenderTest):

    def test_get_headers(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
            'User-Agent': 'Mozilla',
        }
        r = self.request({"url": self.mockurl("getrequest")}, headers=headers)
        self.assertStatusCode(r, 200)
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
        r = self.post({"url": self.mockurl("postrequest")}, headers=headers)
        self.assertStatusCode(r, 200)
        self.assertNotIn("'x-custom-header1': 'some-val1'", r.text)
        self.assertNotIn("'custom-header2': 'some-val2'", r.text)
        self.assertNotIn("x-splash", r.text.lower())
        self.assertNotIn("'content-type': 'application/javascript'", r.text)

    def test_post_user_agent(self):
        r = self.post({"url": self.mockurl("postrequest")}, headers={
            'User-Agent': 'Mozilla',
            'Content-Type': 'application/javascript',  # required by non-proxy POSTs
        })
        self.assertStatusCode(r, 200)
        self.assertNotIn("x-splash", r.text.lower())
        self.assertNotIn("'user-agent': 'Mozilla'", r.text)
        self.assertNotIn("'content-type': 'application/javascript'", r.text)


class FiltersHTMLProxyTest(test_request_filters.FiltersTestHTML):
    request_handler = ProxyRequestHandler
    proxy_test = True


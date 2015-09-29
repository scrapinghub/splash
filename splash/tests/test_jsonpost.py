# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json

import requests
from six.moves.urllib import parse as urlparse
import six

from . import test_render, test_har, test_request_filters, test_runjs


class JsonPostRequestHandler(test_render.DirectRequestHandler):

    def request(self, query, endpoint=None, headers=None):
        assert not isinstance(query, six.string_types)
        endpoint = endpoint or self.endpoint
        url = "http://%s/%s" % (self.host, endpoint)
        data = json.dumps(query)
        _headers = {'content-type': 'application/json'}
        _headers.update(headers or {})
        return requests.post(url, data=data, headers=_headers)

    def post(self, query, endpoint=None, payload=None, headers=None):
        raise NotImplementedError()


class RenderHtmlJsonPostTest(test_render.RenderHtmlTest):
    request_handler = JsonPostRequestHandler

    def test_content_type_with_encoding(self):
        resp = self.request(
            query={"url": self.mockurl("jsrender")},
            headers={"content-type": "application/json; charset=UTF-8"}
        )
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.headers["content-type"].lower(), "text/html; charset=utf-8")
        self.assertTrue("Before" not in resp.text)
        self.assertTrue("After" in resp.text)


class RenderJsonJsonPostTest(test_render.RenderJsonTest):
    request_handler = JsonPostRequestHandler


class HarRenderJsonPostTest(test_har.HarRenderTest):
    request_handler = JsonPostRequestHandler


class FiltersJsonPostTest(test_request_filters.FiltersTestHTML):
    request_handler = JsonPostRequestHandler


class RunJsJsonPostTest(test_runjs.RunJsTest):
    request_handler = JsonPostRequestHandler

    def _runjs_request(self, js_source, endpoint=None, params=None, headers=None):
        query = {
            'url': self.mockurl("jsrender"),
            'script': 1,
            'js_source': js_source,
        }
        query.update(params or {})
        return self.request(query, endpoint=endpoint, headers=headers)


class HttpHeadersTest(test_render.BaseRenderTest):
    request_handler = JsonPostRequestHandler
    use_gzip = False

    def test_get_headers(self):
        headers = {
            'X-Custom-Header1': 'some-val1',
            'Custom-Header2': 'some-val2',
            'Custom-Header3': 'some-val3',
            'User-Agent': 'Mozilla',
            'Connection': 'custom-Header3, Foo, Bar',
        }
        r1 = self.request({
            "url": self.mockurl("getrequest"),
            "headers": headers,
        })
        r2 = self.request({
            "url": self.mockurl("getrequest"),
            "headers": list(headers.items()),
        })

        for r in [r1, r2]:
            self.assertStatusCode(r, 200)
            if six.PY3:
                self.assertIn("b'x-custom-header1': b'some-val1'", r.text)
                self.assertIn("b'custom-header2': b'some-val2'", r.text)
                self.assertIn("b'user-agent': b'Mozilla'", r.text)
            else:
                self.assertIn("'x-custom-header1': 'some-val1'", r.text)
                self.assertIn("'custom-header2': 'some-val2'", r.text)
                self.assertIn("'user-agent': 'Mozilla'", r.text)

            # This is not a proxy request, so Splash shouldn't remove
            # "Connection" header.
            self.assertIn("connection", r.text.lower())
            self.assertIn("custom-header3", r.text.lower())
            self.assertIn("foo", r.text.lower())
            self.assertIn("bar", r.text.lower())

    def test_bad_headers_string(self):
        r = self.request({
            "url": self.mockurl("getrequest"),
            "headers": "foo",
        })
        self.assertJsonError(r, 400, 'BadOption')

    def test_bad_headers_list(self):
        r = self.request({
            "url": self.mockurl("getrequest"),
            "headers": [("foo", ), ("bar", {"hello": "world"})],
        })
        self.assertJsonError(r, 400, 'BadOption')

        r = self.request({
            "url": self.mockurl("getrequest"),
            "headers": [("bar", {"hello": "world"})],
        })
        self.assertJsonError(r, 400, 'BadOption')

    def test_get_user_agent(self):
        headers = {'User-Agent': 'Mozilla123'}
        r = self.request({
            "url": self.mockurl("getrequest"),
            "headers": headers,
        })
        self.assertStatusCode(r, 200)
        if six.PY3:
            self.assertIn("b'user-agent': b'Mozilla123'", r.text)
        else:
            self.assertIn("'user-agent': 'Mozilla123'", r.text)

    def test_connection_user_agent(self):
        headers = {
            'User-Agent': 'Mozilla123',
            'Connection': 'User-agent',
        }
        r = self.request({
            "url": self.mockurl("getrequest"),
            "headers": headers
        })
        self.assertStatusCode(r, 200)

        # this is not a proxy request - don't remove headers
        if six.PY3:
            self.assertIn("b'user-agent': b'Mozilla123'", r.text)
        else:
            self.assertIn("'user-agent': 'Mozilla123'", r.text)
        self.assertIn("mozilla123", r.text.lower())

    def test_user_agent_after_redirect(self):
        headers = {'User-Agent': 'Mozilla123'}
        query = urlparse.urlencode({"url": self.mockurl("getrequest")})
        r = self.request({
            "url": self.mockurl("jsredirect-to?%s" % query),
            "headers": headers,
            "wait": 0.1,
        })
        self.assertStatusCode(r, 200)
        if six.PY3:
            self.assertIn("b'user-agent': b'Mozilla123'", r.text)
        else:
            self.assertIn("'user-agent': 'Mozilla123'", r.text)

    def test_cookie(self):
        r = self.request({
            "url": self.mockurl("get-cookie?key=foo"),
            "headers": {'Cookie': 'foo=bar'},
        })
        self.assertStatusCode(r, 200)
        self.assertIn("bar", r.text)

    def test_http_POST_request_from_splash(self):
        formbody = {"param1": "one", "param2": "two"}

        r = self.request({
            "url": self.mockurl("postrequest"),
            "body": six.moves.urllib.parse.urlencode(formbody),
            "http_method": "POST"
        })
        self.assertStatusCode(r, 200)
        self.assertTrue(
            "param2=two&amp;param1=one" in r.text or
            "param1=one&amp;param2=two" in r.text
        , r.text)

    def test_http_go_POST_missing_method(self):
        formbody = {"param1": "one", "param2": "two"}
        r = self.request({
            "url": self.mockurl("postrequest"),
            "body": six.moves.urllib.parse.urlencode(formbody),
            "baseurl": "foo"
        })
        self.assertStatusCode(r, 400)
        self.assertIn('GET request should not have a body', r.text)

    def test_bad_http_method(self):
        r = self.request({
            "url": self.mockurl("postrequest"),
            "http_method": "FOO"
        })
        self.assertStatusCode(r, 400)
        self.assertIn('Unsupported HTTP method FOO', r.text)

    # def test_cookie_after_redirect(self):
    #     headers = {'Cookie': 'foo=bar'}
    #     query = urlparse.urlencode({"url": self.mockurl("get-cookie?key=foo")})
    #     r = self.request({
    #         "url": self.mockurl("jsredirect-to?%s" % query),
    #         "headers": headers,
    #         "wait": 0.1,
    #     })
    #     self.assertStatusCode(r, 200)
    #     self.assertIn("bar", r.text)


class RenderInvalidJsonJsonPostTest(test_render.BaseRenderTest):
    request_handler = test_render.DirectRequestHandler

    def test_invalid_json_returns_400(self):
        invalid_json = "\'{"
        headers = {"content-type": "application/json; charset=UTF-8"}
        resp = self.post({}, payload=invalid_json, headers=headers)
        data = self.assertJsonError(resp, 400, 'BadOption')
        self.assertEqual(data['info']['type'], 'invalid_json')

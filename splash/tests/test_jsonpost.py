# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import urllib
import requests
from . import test_render, test_har, test_request_filters, test_runjs


class JsonPostRequestHandler(test_render.DirectRequestHandler):

    def request(self, query, endpoint=None, headers=None):
        assert not isinstance(query, basestring)
        endpoint = endpoint or self.endpoint
        url = "http://%s/%s" % (self.host, endpoint)
        data = json.dumps(query, encoding='utf8')
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
        self.assertStatusCode(r, 400)

    def test_bad_headers_list(self):
        r = self.request({
            "url": self.mockurl("getrequest"),
            "headers": [("foo", ), ("bar", {"hello": "world"})],
        })
        self.assertStatusCode(r, 400)

        r = self.request({
            "url": self.mockurl("getrequest"),
            "headers": [("bar", {"hello": "world"})],
        })
        self.assertStatusCode(r, 400)

    def test_get_user_agent(self):
        headers = {'User-Agent': 'Mozilla123'}
        r = self.request({
            "url": self.mockurl("getrequest"),
            "headers": headers,
        })
        self.assertStatusCode(r, 200)
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
        self.assertIn("'user-agent': 'Mozilla123'", r.text)
        self.assertIn("mozilla123", r.text.lower())

    def test_user_agent_after_redirect(self):
        headers = {'User-Agent': 'Mozilla123'}
        query = urllib.urlencode({"url": self.mockurl("getrequest")})
        r = self.request({
            "url": self.mockurl("jsredirect-to?%s" % query),
            "headers": headers,
            "wait": 0.1,
        })
        self.assertStatusCode(r, 200)
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
            "formdata": formbody,
            "body": urllib.urlencode(formbody),
            "http_method": "POST"
        })
        self.assertStatusCode(r, 200)
        self.assertIn("param2=two&amp;param1=one", r.text)


    def test_http_go_POST_missing_method(self):
        formbody = {"param1": "one", "param2": "two"}
        r = self.request({
            "url": self.mockurl("postrequest"),
            "body": urllib.urlencode(formbody),
            "baseurl": "foo"
        })
        self.assertStatusCode(r, 400)
        self.assertIn('Bad HTTP method. Request has body but method is GET', r.text)

    def test_bad_http_method(self):
        r = self.request({
            "url": self.mockurl("postrequest"),
            "http_method": "FOO"
        })
        self.assertStatusCode(r, 400)
        self.assertIn("not allowed", r.text)

    # def test_cookie_after_redirect(self):
    #     headers = {'Cookie': 'foo=bar'}
    #     query = urllib.urlencode({"url": self.mockurl("get-cookie?key=foo")})
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
        self.assertStatusCode(resp, 400)
        self.assertIn("Invalid JSON", resp.text)

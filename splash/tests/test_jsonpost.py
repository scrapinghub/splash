# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import requests
from . import test_render, test_har, test_request_filters, test_runjs


class JsonPostRequestHandler(test_render.DirectRequestHandler):

    def request(self, query, render_format=None, headers=None):
        assert not isinstance(query, basestring)
        render_format = render_format or self.render_format
        url = "http://%s/render.%s" % (self.host, render_format)
        data = json.dumps(query, encoding='utf8')
        _headers = {'content-type': 'application/json'}
        _headers.update(headers or {})
        return requests.post(url, data=data, headers=_headers)

    def post(self, query, render_format=None, payload=None, headers=None):
        raise NotImplementedError()


class RenderHtmlJsonPostTest(test_render.RenderHtmlTest):
    request_handler = JsonPostRequestHandler

    def test_content_type_with_encoding(self):
        resp = self.request(
            query={"url": self.mockurl("jsrender")},
            headers={"content-type": "application/json; charset=UTF-8"}
        )
        self.assertEqual(resp.status_code, 200)
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

    def _runjs_request(self, js_source, render_format=None, params=None, headers=None):
        query = {
            'url': self.mockurl("jsrender"),
            'script': 1,
            'js_source': js_source,
        }
        query.update(params or {})
        return self.request(query, render_format=render_format, headers=headers)


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
            self.assertEqual(r.status_code, 200)
            self.assertIn("'x-custom-header1': 'some-val1'", r.text)
            self.assertIn("'custom-header2': 'some-val2'", r.text)
            self.assertIn("'user-agent': 'Mozilla'", r.text)

            # Connection header is handled correctly - this is not a proxy request,
            # so don't remove it
            self.assertIn("connection", r.text.lower())
            self.assertIn("custom-header3", r.text.lower())
            self.assertIn("foo", r.text.lower())
            self.assertIn("bar", r.text.lower())

    def test_get_user_agent(self):
        headers = {'User-Agent': 'Mozilla123'}
        r = self.request({
            "url": self.mockurl("getrequest"),
            "headers": headers,
        })
        self.assertEqual(r.status_code, 200)
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
        self.assertEqual(r.status_code, 200)

        # this is not a proxy request - don't remove headers
        self.assertIn("'user-agent': 'Mozilla123'", r.text)
        self.assertIn("mozilla123", r.text.lower())

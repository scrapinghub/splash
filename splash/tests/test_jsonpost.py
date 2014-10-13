# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import requests
from . import test_render, test_har, test_request_filters


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

# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import requests
from .test_render import DirectRequestHandler, RenderHtmlTest, RenderJsonTest
from .test_har import HarRenderTest
from .test_request_filters import FiltersTestHTML


class JsonPostRequestHandler(DirectRequestHandler):

    def request(self, query, render_format=None, headers=None):
        assert not isinstance(query, basestring)
        render_format = render_format or self.render_format
        url = "http://%s/render.%s" % (self.host, render_format)
        data = json.dumps(query, encoding='utf8')
        headers = headers.copy() if headers is not None else {}
        headers['content-type'] = 'application/json'
        return requests.post(url, data=data, headers=headers)

    def post(self, query, render_format=None, payload=None, headers=None):
        raise NotImplementedError()


class RenderHtmlJsonPostTest(RenderHtmlTest):
    request_handler = JsonPostRequestHandler


class RenderJsonJsonPostTest(RenderJsonTest):
    request_handler = JsonPostRequestHandler


class HarRenderJsonPostTest(HarRenderTest):
    request_handler = JsonPostRequestHandler


class FiltersJsonPostTest(FiltersTestHTML):
    request_handler = JsonPostRequestHandler

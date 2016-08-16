# -*- coding: utf-8 -*-
from __future__ import absolute_import
import base64

import requests

from splash.har.utils import get_response_body_bytes
from splash.tests.test_execute import BaseLuaRenderTest


class ResponseTrackingTest(BaseLuaRenderTest):
    def assertHarEntriesLength(self, har, length):
        entries = har['log']['entries']
        assert len(entries) == length
        return entries

    def assertNoContent(self, entry):
        assert 'text' not in entry['response']['content']

    def assertBase64Content(self, entry, body):
        assert entry['response']['content']['encoding'] == 'base64'
        assert get_response_body_bytes(entry['response']) == body

    def test_enable_response_body(self):
        url = self.mockurl('show-image')
        resp = self.request_lua("""
        function main(splash)
            splash:on_request(function(req)
                if req.url:find(".gif") ~= nil then
                    req:enable_response_body()
                end
            end)

            local bodies = {}
            splash:on_response(function(resp, req)
                bodies[resp.url] = resp.body
            end)

            assert(splash:go(splash.args.url))
            return {har=splash:har(), bodies=bodies}
        end
        """, {'url': url})
        self.assertStatusCode(resp, 200)
        data = resp.json()

        bodies = data['bodies']
        assert len(bodies) == 1
        url = list(bodies.keys())[0]
        assert "slow.gif" in url
        img_gif = requests.get(self.mockurl("slow.gif?n=0")).content
        body = base64.b64decode(bodies[url])
        assert body == img_gif

        entries = self.assertHarEntriesLength(data['har'], 2)
        self.assertNoContent(entries[0])
        self.assertBase64Content(entries[1], img_gif)

    def test_response_body_enabled(self):
        url = self.mockurl('show-image')
        resp = self.request_lua("""
        treat = require('treat')
        function main(splash)
            splash.response_body_enabled = true
            assert(splash:go(splash.args.url))
            local har1 = splash:har{reset=true}
            splash.response_body_enabled = false
            assert(splash:go(splash.args.url))
            local har2 = splash:har()
            return {
                har = treat.as_array({har1, har2}),
                enabled2 = splash.response_body_enabled,
            }
        end
        """, {'url': url})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        assert data['enabled2'] is False

        img_gif = requests.get(self.mockurl("slow.gif?n=0")).content
        resp = requests.get(self.mockurl('show-image')).content

        entries = self.assertHarEntriesLength(data['har'][0], 2)
        body = get_response_body_bytes(entries[0]['response'])
        assert body[:50] == resp[:50]  # there is some randomness in the end
        self.assertBase64Content(entries[1], img_gif)

        entries = self.assertHarEntriesLength(data['har'][1], 2)
        self.assertNoContent(entries[0])
        self.assertNoContent(entries[1])


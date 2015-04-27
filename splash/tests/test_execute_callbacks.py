# -*- coding: utf-8 -*-
from __future__ import absolute_import
from .test_execute import BaseLuaRenderTest


class OnRequestTest(BaseLuaRenderTest):
    def test_request_log(self):
        resp = self.request_lua("""
        function main(splash)
            local urls = {}
            local requests = {}
            splash:on_request(function(request)
                requests[#requests+1] = request.info
                urls[#urls+1] = request.url
            end)
            splash:go(splash.args.url)
            return requests, urls
        end
        """, {'url': self.mockurl("show-image")})
        self.assertStatusCode(resp, 200)
        requests, urls = resp.json()

        # FIXME: it should return lists, and indices should be integer
        self.assertIn("show-image", urls['1'])
        self.assertIn("slow.gif", urls['2'])

        self.assertEqual(requests['1']['method'], 'GET')
        self.assertEqual(requests['1']['url'], urls['1'])


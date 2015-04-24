# -*- coding: utf-8 -*-
from __future__ import absolute_import
from .test_execute import BaseLuaRenderTest


class OnRequestTest(BaseLuaRenderTest):
    def test_request_log(self):
        resp = self.request_lua("""
        function main(splash)
            local urls = {}
            splash:on_request(function(request)
                urls[#urls+1] = request.url
            end)
            splash:go(splash.args.url)
            return urls
        end
        """, {'url': self.mockurl("show-image")})
        self.assertStatusCode(resp, 200)
        urls = resp.json()
        print(urls)
        self.assertIn("show-image", urls['1'])
        self.assertIn("slow.gif", urls['2'])

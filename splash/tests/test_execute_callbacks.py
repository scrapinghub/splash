# -*- coding: utf-8 -*-
from __future__ import absolute_import
import base64
from io import BytesIO
from PIL import Image
from splash.tests.test_proxy import BaseHtmlProxyTest
from .test_execute import BaseLuaRenderTest


class OnRequestTest(BaseLuaRenderTest, BaseHtmlProxyTest):
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

    def test_abort_request(self):
        resp = self.request_lua("""
        function main(splash)
            splash:on_request(function(request)
                if string.find(request.url, "gif") ~= nil then
                    request:abort()
                end
            end)
            splash:go(splash.args.url)
            return {har=splash:har(), png=splash:png()}
        end
        """, {'url': self.mockurl("show-image")})
        self.assertStatusCode(resp, 200)
        data = resp.json()

        # the rendered image is not black (gif is not rendered)
        img = Image.open(BytesIO(base64.b64decode(data['png'])))
        self.assertEqual((255, 255, 255, 255), img.getpixel((10, 10)))

        # gif file is not in HAR log
        urls = [e['request']['url'] for e in data['har']['log']['entries']]
        self.assertTrue(any('show-image' in url for url in urls), urls)
        self.assertFalse(any('.gif' in url for url in urls), urls)

    def test_set_url(self):
        url = self.mockurl("http-redirect?code=302")
        new_url = self.mockurl("jsrender")
        resp = self.request_lua("""
        function main(splash)
            splash:on_request(function(request)
                if request.url == splash.args.url then
                    request:set_url(splash.args.new_url)
                end
            end)
            splash:go(splash.args.url)
            return splash:html()
        end
        """, {'url': url, 'new_url': new_url})
        self.assertStatusCode(resp, 200)
        self.assertIn('After', resp.content)

    def test_set_proxy(self):
        proxy_port = self.ts.mock_proxy_port
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            local html_1 = splash:html()

            splash:on_request(function(request)
                request:set_proxy{
                    host="0.0.0.0",
                    port=splash.args.proxy_port
                }
            end)

            assert(splash:go(splash.args.url))
            local html_2 = splash:html()
            return html_1, html_2
        end
        """, {'url': self.mockurl("jsrender"), 'proxy_port': proxy_port})
        self.assertStatusCode(resp, 200)
        html_1, html_2 = resp.json()
        self.assertNotProxied(html_1)
        self.assertProxied(html_2)

    def test_request_outside_callback(self):
        resp = self.request_lua("""
        function main(splash)
            local req = nil
            splash:on_request(function(request)
                req = request
            end)
            assert(splash:go(splash.args.url))
            req:abort()
            return "ok"
        end
        """, {'url': self.mockurl("jsrender")})
        self.assertStatusCode(resp, 400)
        self.assertErrorLineNumber(resp, 8)
        self.assertIn("request is used outside a callback", resp.content)

    def test_set_header(self):
        resp = self.request_lua("""
        function main(splash)
            splash:on_request(function(request)
                request:set_header("User-Agent", "Fooozilla")
                request:set_header{name="Custom-header", value="some-val"}
            end)
            splash:go(splash.args.url)
            return splash:html()
        end
        """, {'url': self.mockurl("getrequest")})
        self.assertStatusCode(resp, 200)

        self.assertIn("'custom-header': 'some-val'", resp.text)
        self.assertIn("'user-agent': 'Fooozilla'", resp.text)


class OnResponseTest(BaseLuaRenderTest, BaseHtmlProxyTest):
    def test_abort_on_response_headers(self):
        resp = self.request_lua("""
        function main(splash)
            splash:on_response_headers(function(response, request)
                request:abort()
            end)
            res = splash:http_get(splash.args.url)
            return res
        end
        """, {'url': self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        self.assertFalse(resp.json().get("content").get("text"))

# -*- coding: utf-8 -*-
from __future__ import absolute_import
import base64
from io import BytesIO

from PIL import Image
import six
from six.moves.urllib.parse import urlencode
import pytest

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
        self.assertIn('After', resp.content.decode('utf-8'))

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
        self.assertIn("request is used outside a callback", resp.content.decode('utf-8'))

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


        if six.PY3:
            self.assertIn("b'custom-header': b'some-val'", resp.text)
            self.assertIn("b'user-agent': b'Fooozilla'", resp.text)
        else:
            self.assertIn("'custom-header': 'some-val'", resp.text)
            self.assertIn("'user-agent': 'Fooozilla'", resp.text)


class OnResponseHeadersTest(BaseLuaRenderTest, BaseHtmlProxyTest):
    def test_get_header(self):
        resp = self.request_lua("""
        function main(splash)
            local header_value = nil
            splash:on_response_headers(function(response)
                header_value = response.headers['Content-Type']
            end)
            res = splash:http_get(splash.args.url)
            return header_value
        end
        """, {'url': self.mockurl("jsrender")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "text/html")

    def test_abort_on_response_headers(self):
        resp = self.request_lua("""
        function main(splash)
            splash:on_response_headers(function(response)
                if response.headers['Content-Type'] == 'text/html' then
                    response:abort()
                end
            end)
            res = splash:http_get(splash.args.url)
            return res
        end
        """, {'url': self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        self.assertFalse(resp.json().get("content").get("text"))

    def test_response_used_outside_callback(self):
        resp = self.request_lua("""
        function main(splash)
            local res = nil
            splash:on_response_headers(function(response)
                res = response
            end)
            splash:http_get(splash.args.url)
            res:abort()
            return "ok"
        end
        """, {'url': self.mockurl("jsrender")})
        self.assertStatusCode(resp, 400)
        self.assertIn("response is used outside callback", resp.text)

    def test_get_headers(self):
        headers = {
            "Foo": "bar",
            "X-Proxy-Something": "1234",
            "X-Content-Type-Options": "nosniff"
        }
        mocked_url = self.mockurl("set-header?" + urlencode(headers))
        resp = self.request_lua("""
        function main(splash)
            local headers = nil
            splash:on_response_headers(function(response)
                headers = response.headers
                response.abort()
            end)
            splash:http_get(splash.args.url)
            return headers
        end""", {"url": mocked_url})

        result = resp.json()

        self.assertStatusCode(resp, 200)

        for k, v in headers.items():
            self.assertIn(k, result)
            self.assertEqual(result[k], headers[k])

    def test_other_response_attr(self):
        headers = {
            "Foo": "bar",
        }
        mocked_url = self.mockurl("set-header?" + urlencode(headers))
        some_attrs = {
            "url": (six.text_type, mocked_url),
            "status": (int, 200),
            "info": (dict, {}),
            "ok": (bool, True),
        }

        resp = self.request_lua("""
        function main(splash)
            local all_attrs = {}
            local attr_names = {"url", "status", "info", "ok", "request"}
            splash:on_response_headers(function(response)
                for key, value in pairs(attr_names) do
                    all_attrs[value] = response[value]
                end
            end)
            splash:http_get(splash.args.url)
            return all_attrs
        end""", {"url": mocked_url})
        self.assertStatusCode(resp, 200)
        result = resp.json()

        for k, v in some_attrs.items():
            self.assertIn(k, result)
            self.assertIsInstance(result[k], v[0])
            if v[1]:
                self.assertEqual(result[k], v[1])

    def test_request_in_callback(self):
        mocked_url = self.mockurl("set-header?" + urlencode({"alfa": "beta"}))
        resp = self.request_lua("""
        function main(splash)
            splash:on_response_headers(function(response)
                req_info = {}
                for key, value in pairs(response.request) do
                    req_info[key] = response.request[key]
                end
            end)
            splash:on_request(function(request)
                request:set_header("hello", "world")
            end)
            splash:http_get(splash.args.url)
            return req_info
        end""", {"url": mocked_url})
        self.assertStatusCode(resp, 200)
        resp = resp.json()
        for elem in ["method", "url", "headers"]:
            self.assertIn(elem, resp)
        self.assertEqual(resp["url"], mocked_url)
        self.assertEqual(resp["method"], "GET")
        self.assertEqual(resp["headers"], {"hello": "world"})


class OnResponseTest(BaseLuaRenderTest):
    maxDiff = 2000

    def test_on_response(self):
        url = self.mockurl("show-image")
        resp = self.request_lua("""
        function main(splash)
            local result = {}
            splash:on_response(function(response)
                local resp_info = {
                    ctype = response.headers['Content-Type'],
                    url = response.url,
                    info = response.info,
                    status = response.status,
                    request = response.request,
                }
                result[#result+1] = resp_info
            end)
            assert(splash:go(splash.args.url))
            return {
                result = result,
                har = splash:har(),
            }
        end
        """, {'url': url})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(len(data['result']), 2, data['result'])

        e1, e2 = data['result']['1'], data['result']['2']

        entries = data['har']['log']['entries']
        self.assertEqual(len(entries), 2, entries)
        h1, h2 = entries[0], entries[1]

        self.assertEqual(e1['info'], h1['response'])
        self.assertEqual(e2['info'], h2['response'])

        self.assertEqual(e1['ctype'], 'text/html')
        self.assertEqual(e2['ctype'], 'image/gif')

        self.assertEqual(e1['status'], 200)
        self.assertEqual(e2['status'], 200)

        self.assertEqual(e1['url'], url)

        self.assertEqual(e1['request']['url'], url)
        self.assertEqual(
            e1['request']['headers'],
            {el['name']: el['value'] for el in h1['request']['headers']}
        )
        self.assertEqual(e1['request']['method'], 'GET')
        self.assertEqual(e1['request']['cookies'], h1['request']['cookies'])

    @pytest.mark.xfail(reason="async support for splash:on_response "
                              "is not implemented yet")
    def test_async_wait(self):
        resp = self.request_lua("""
        function main(splash)
            local value = 0
            splash:on_response(function(response)
                splash:wait(0.1)
                value = value + 1
            end)
            assert(splash:go(splash.args.url))
            local v1 = value
            splash:wait(0.3)
            local v2 = value
            return {v1, v2}
        end
        """, {'url': self.mockurl("show-image")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'1': 0, '2': 2})

    def test_call_later_from_on_response(self):
        resp = self.request_lua("""
        function main(splash)
            local htmls = {}
            splash:on_response(function(response)
                htmls[#htmls+1] = {before=true, html=splash:html()}
                splash:call_later(function()
                    htmls[#htmls+1] = {before=false, html=splash:html()}
                end, 0.1)
            end)
            assert(splash:go(splash.args.url))
            splash:wait(0.2)
            return htmls
        end
        """, {'url': self.mockurl("jsredirect")})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(len(data), 4, data)
        self.assertEqual(
            [data[k]['before'] for k in '1234'],
            [True, True, False, False]
        )
        self.assertNotIn("JS REDIRECT TARGET", data['1']['html'])
        self.assertNotIn("JS REDIRECT TARGET", data['2']['html'])
        self.assertIn("JS REDIRECT TARGET", data['3']['html'])
        self.assertIn("JS REDIRECT TARGET", data['4']['html'])


class CallLaterTest(BaseLuaRenderTest):
    def test_call_later(self):
        resp = self.request_lua("""
        function main(splash)
            local x = 1
            splash:call_later(function() x = 2 end, 0.1)
            local x1 = x
            splash:wait(0.2)
            local x2 = x
            return {x1=x1, x2=x2}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'x1': 1, 'x2': 2})

    def test_zero_delay(self):
        resp = self.request_lua("""
        function main(splash)
            local x = 1
            splash:call_later(function() x = 2 end)
            local x1 = x
            splash:wait(0.01)
            local x2 = x
            return {x1=x1, x2=x2}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'x1': 1, 'x2': 2})

    def test_bad_delay(self):
        resp = self.request_lua("""
        function main(splash)
            splash:call_later(function() x = 2 end, -1)
        end
        """)
        self.assertErrorLineNumber(resp, 3)

        resp = self.request_lua("""
        function main(splash)
            splash:call_later(function() x = 2 end, 'foo')
        end
        """)
        self.assertErrorLineNumber(resp, 3)

    def test_bad_callback(self):
        resp = self.request_lua("""
        function main(splash)
            splash:call_later(5, 1.0)
        end
        """)
        self.assertErrorLineNumber(resp, 3)

    def test_attributes_not_exposed(self):
        resp = self.request_lua("""
        function main(splash)
            local timer = splash:call_later(function() end, 1.0)
            return {
                timer=timer.timer,
                lua=timer.lua,
                singleShot=timer.singleShot,
            }
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {})

    def test_cancel(self):
        resp = self.request_lua("""
        function main(splash)
            local x = 1
            local timer = splash:call_later(function() x = 2 end, 0.1)
            timer:cancel()
            local x1 = x
            splash:wait(0.2)
            local x2 = x
            return {x1=x1, x2=x2}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'x1': 1, 'x2': 1})

    def test_is_pending(self):
        resp = self.request_lua("""
        function main(splash)
            local x = 1
            local timer = splash:call_later(function() x = 2 end, 0.1)
            local r1 = timer:is_pending()
            splash:wait(0.2)
            local r2 = timer:is_pending()
            return {r1=r1, r2=r2}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'r1': True, 'r2': False})

    def test_is_pending_async(self):
        resp = self.request_lua("""
        function main(splash)
            local timer = splash:call_later(function()
                splash:wait(1.0)
            end)
            splash:wait(0.1)
            -- timer should be 'executing', not pending at this point
            return {pending=timer:is_pending()}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'pending': False})

    def test_call_later_chain(self):
        resp = self.request_lua("""
        function main(splash)
            local x = 0
            local function tick()
               x = x + 1
               if x < 5 then
                   splash:call_later(tick, 0.01)
               end
            end
            splash:call_later(tick, 0.0)
            local x1 = x
            splash:wait(0.2)
            local x2 = x
            splash:wait(0.2)
            local x3 = x
            return {x1=x1, x2=x2, x3=x3}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'x1': 0, 'x2': 5, 'x3': 5})

    def test_wait(self):
        resp = self.request_lua("""
        function main(splash)
            local x = 1
            splash:call_later(function()
                x = 2
                splash:wait(0.2)
                x = 3
            end, 0.0)
            local x1 = x
            splash:wait(0.1)
            local x2 = x
            splash:wait(0.15)
            local x3 = x
            return {x1=x1, x2=x2, x3=x3}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'x1': 1, 'x2': 2, 'x3': 3})

    def test_error_unhandled_reraise(self):
        resp = self.request_lua("""
        function main(splash)
            local timer = splash:call_later(function()
                error("hello")
            end, 0.1)
            splash:wait(0.2)
            timer:reraise()
            return "ok"
        end
        """)
        self.assertErrorLineNumber(resp, 4)

    def test_error_unhandled_no_reraise(self):
        resp = self.request_lua("""
        function main(splash)
            local timer = splash:call_later(function() error("hello") end, 0.1)
            splash:wait(0.2)
            return "ok"
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "ok")

    def test_error_handled_in_callback(self):
        resp = self.request_lua("""
        function main(splash)
            local status = "unknown"
            local timer = splash:call_later(function()
                if pcall(function() error("hello") end) then
                    status = "no_errors"
                else
                    status = "error"
                end
            end, 0.1)
            splash:wait(0.2)
            timer:reraise()
            return status
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "error")

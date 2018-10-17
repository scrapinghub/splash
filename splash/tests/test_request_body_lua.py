# -*- coding: utf-8 -*-

from splash.tests.test_execute import BaseLuaRenderTest


class RequestBodyLuaTest(BaseLuaRenderTest):
    def test_request_body_enabled(self):
        url = self.mockurl('jspost')
        resp = self.request_lua("""
        treat = require('treat')
        function main(splash)
            splash.request_body_enabled = true
            assert(splash:go(splash.args.url))
            splash:wait(0.1)
            local har1 = splash:har{reset=true}
            local enabled1 = splash.request_body_enabled
            splash.request_body_enabled = false
            assert(splash:go(splash.args.url))
            splash:wait(0.1)
            local har2 = splash:har()
            local enabled2 = splash.request_body_enabled
            return {
                har = treat.as_array({har1, har2}),
                enabled1 = enabled1,
                enabled2 = enabled2
            }
        end
        """, {'url': url})
        self.assertStatusCode(resp, 200)
        data = resp.json()

        assert data['enabled1']
        assert not data['enabled2']

        har1 = data['har'][0]['log']['entries']
        assert 'postData' in har1[1]['request']

        har2 = data['har'][1]['log']['entries']
        assert 'postData' not in har2[1]['request']

    def test_request_info_on_request_postdata(self):
        url = self.mockurl('jspost')
        resp = self.request_lua("""
        function main(splash)
            splash.request_body_enabled = true

            local request_info = nil

            splash:on_request(function(request)
                if request.method == "POST" then
                    request_info = request.info
                end
            end)

            assert(splash:go(splash.args.url))
            splash:wait(0.1)
            
            local post_data = request_info["postData"]
            return {
                text = post_data["text"],
                mime_type = post_data["mimeType"]
            }
        end
        """, {'url': url})
        self.assertStatusCode(resp, 200)
        data = resp.json()

        assert data['text'] == "hidden-field=i-am-hidden&a-field=field+value"
        assert data['mime_type'] == "application/x-www-form-urlencoded"

    def test_request_info_on_response_postdata(self):
        url = self.mockurl('jspost')
        resp = self.request_lua("""
        function main(splash)
            splash.request_body_enabled = true

            local request_info = nil

            splash:on_response(function(response)
                if response.request.method == "POST" then
                    request_info = response.request.info
                end
            end)

            assert(splash:go(splash.args.url))
            splash:wait(0.1)

            local post_data = request_info["postData"]
            return {
                text = post_data["text"],
                mime_type = post_data["mimeType"]
            }
        end
        """, {'url': url})
        self.assertStatusCode(resp, 200)
        data = resp.json()

        assert data['text'] == "hidden-field=i-am-hidden&a-field=field+value"
        assert data['mime_type'] == "application/x-www-form-urlencoded"

# -*- coding: utf-8 -*-
from __future__ import absolute_import
import hashlib

from .test_render import BaseRenderTest
from .test_execute import BaseLuaRenderTest
from .test_jsonpost import JsonPostRequestHandler


class RenderHtmlArgumentCachingTest(BaseRenderTest):
    endpoint = 'render.html'

    def test_cache_url(self):
        # make a save_args request
        resp = self.request({
            "url": self.mockurl('jsrender'),
            "wait": 0.5,
            "save_args": "url,wait",
        })
        self.assertStatusCode(resp, 200)
        self.assertIn("After", resp.text)

        # use load_args to avoid sending parameter values
        header = resp.headers['X-Splash-Saved-Arguments']
        resp2 = self.request({"load_args": header})
        self.assertStatusCode(resp2, 200)
        assert resp2.text == resp.text

        # clear cache
        resp3 = self.post({}, endpoint="_gc")
        self.assertStatusCode(resp3, 200)
        data = resp3.json()
        assert data['cached_args_removed'] >= 2
        assert data['pyobjects_collected'] > 0
        assert data['status'] == 'ok'

        # check that argument cache is cleared
        resp4 = self.request({"load_args": header})
        data = self.assertJsonError(resp4, 498, 'ExpiredArguments')
        assert set(data['info']['expired']) == {'wait', 'url'}


class ArgumentCachingTest(BaseLuaRenderTest):
    request_handler = JsonPostRequestHandler

    def test_cache_args(self):
        resp = self.request_lua("""
        function main(splash)
            return {foo=splash.args.foo, baz=splash.args.baz}
        end
        """, {
            "save_args": ["lua_source", "foo", "bar"],
            "foo": "hello",
            "baz": "world",
        })
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"foo": "hello", "baz": "world"})

        hashes = dict(
            h.split("=", 1) for h in
            resp.headers['X-Splash-Saved-Arguments'].split(";")
        )
        resp2 = self.request({"load_args": hashes, "baz": "!"})
        self.assertStatusCode(resp2, 200)
        self.assertEqual(resp2.json(), {"foo": "hello", "baz": "!"})

        hashes["foo"] = hashlib.sha1(b"invalid").hexdigest()
        resp3 = self.request({"load_args": hashes, "baz": "!"})
        data = self.assertJsonError(resp3, 498, "ExpiredArguments")
        self.assertEqual(data['info'], {'expired': ['foo']})

    def test_bad_save_args(self):
        resp = self.request_lua("function main(splash) return 'hi' end", {
            "save_args": {"lua_source": "yes"},
        })
        self.assertBadArgument(resp, "save_args")

        resp = self.request_lua("function main(splash) return 'hi' end", {
            "save_args": ["foo", 324],
        })
        self.assertBadArgument(resp, "save_args")

    def test_bad_load_args(self):
        resp = self.request({"load_args": "foo"})
        self.assertBadArgument(resp, "load_args")

        resp = self.request({"load_args": [("foo", "bar")]})
        self.assertBadArgument(resp, "load_args")

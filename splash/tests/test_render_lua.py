# -*- coding: utf-8 -*-
from __future__ import absolute_import

from . import test_render


class LuaRenderTest(test_render.BaseRenderTest):
    render_format = 'lua'

    def request_lua(self, code):
        return self.request({"lua_source": code})

    def test_return_json(self):
        resp = self.request_lua("""
        function main(splash)
          local obj = {key="value"}
          return {mystatus="ok", number=5, obj=obj, bool=true, bool2=false}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.headers['content-type'], 'application/json')
        self.assertEqual(resp.json(), {
            "mystatus": "ok",
            "number": 5,
            "obj": {"key": "value"},
            "bool": True,
            "bool2": False,
        })

    def test_content_type(self):
        resp = self.request_lua("""
        function main(splash)
          splash.result_content_type = 'text/plain'
          return "hi!"
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.headers['content-type'], 'text/plain')
        self.assertEqual(resp.text, 'hi!')

    def test_empty(self):
        resp = self.request_lua("function main(splash) end")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "")

        resp = self.request_lua("function main() end")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "")

    def test_no_main(self):
        resp = self.request_lua("x=1")
        self.assertStatusCode(resp, 400)

    def test_bad_main(self):
        resp = self.request_lua("main=1")
        self.assertStatusCode(resp, 400)

    def test_ugly_main(self):
        resp = self.request_lua("main={coroutine=123}")
        self.assertStatusCode(resp, 400)

    def test_nasty_main(self):
        resp = self.request_lua("""
        main = {coroutine=function()
          return {
            send=function() end,
            next=function() end
          }
        end}
        """)
        self.assertStatusCode(resp, 400)

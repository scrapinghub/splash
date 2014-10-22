# -*- coding: utf-8 -*-
from __future__ import absolute_import

from . import test_render

class BaseLuaRenderTest(test_render.BaseRenderTest):
    render_format = 'lua'

    def request_lua(self, code):
        return self.request({"lua_source": code})


class LuaRenderTest(BaseLuaRenderTest):

    def test_return_json(self):
        resp = self.request_lua("""
        function main(splash)
          local obj = {key="value"}
          return {
            mystatus="ok",
            number=5,
            float=-0.5,
            obj=obj,
            bool=true,
            bool2=false,
            missing=nil
          }
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.headers['content-type'], 'application/json')
        self.assertEqual(resp.json(), {
            "mystatus": "ok",
            "number": 5,
            "float": -0.5,
            "obj": {"key": "value"},
            "bool": True,
            "bool2": False,
        })

    def test_unicode(self):
        resp = self.request_lua(u"""
        function main(splash) return {key="значение"} end
        """.encode('utf8'))

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.headers['content-type'], 'application/json')
        self.assertEqual(resp.json(), {"key": u"значение"})

    def test_unicode_direct(self):
        resp = self.request_lua(u"""
        function main(splash)
          return 'привет'
        end
        """.encode('utf8'))
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, u"привет")
        self.assertEqual(resp.headers['content-type'], 'text/plain; charset=utf-8')

    def test_number(self):
        resp = self.request_lua("function main(splash) return 1 end")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "1")
        self.assertEqual(resp.headers['content-type'], 'text/plain; charset=utf-8')

    def test_bool(self):
        resp = self.request_lua("function main(splash) return true end")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "True")
        self.assertEqual(resp.headers['content-type'], 'text/plain; charset=utf-8')

    def test_empty(self):
        resp = self.request_lua("function main(splash) end")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "")

        resp = self.request_lua("function main() end")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "")


class ContentTypeTest(BaseLuaRenderTest):
    def test_content_type(self):
        resp = self.request_lua("""
        function main(splash)
          splash:set_result_content_type('text/plain')
          return "hi!"
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.headers['content-type'], 'text/plain')
        self.assertEqual(resp.text, 'hi!')

    def test_bad_content_type(self):
        resp = self.request_lua("""
        function main(splash)
          splash:set_result_content_type(55)
          return "hi!"
        end
        """)
        self.assertStatusCode(resp, 400)
        self.assertIn("argument must be a string", resp.text)

        resp = self.request_lua("""
        function main(splash)
          splash:set_result_content_type()
          return "hi!"
        end
        """)
        self.assertStatusCode(resp, 400)
        self.assertIn("set_result_content_type", resp.text)

    def test_bad_content_type_func(self):
        resp = self.request_lua("""
        function main(splash)
          splash:set_result_content_type(function () end)
          return "hi!"
        end
        """)
        self.assertStatusCode(resp, 400)
        self.assertIn("argument must be a string", resp.text)


class EntrypointTest(BaseLuaRenderTest):

    def test_no_main(self):
        resp = self.request_lua("x=1")
        self.assertStatusCode(resp, 400)
        self.assertIn("function is not found", resp.text)

    def test_bad_main(self):
        resp = self.request_lua("main=1")
        self.assertStatusCode(resp, 400)
        self.assertIn("is not a function", resp.text)

    def test_ugly_main(self):
        resp = self.request_lua("main={coroutine=123}")
        self.assertStatusCode(resp, 400)
        self.assertIn("is not a function", resp.text)

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
        self.assertIn("is not a function", resp.text)


class ErrorsTest(BaseLuaRenderTest):

    def test_syntax_error(self):
        resp = self.request_lua("function main(splash) sdhgfsajhdgfjsahgd end")
        self.assertStatusCode(resp, 400)

    def test_syntax_error_toplevel(self):
        resp = self.request_lua("sdg; function main(splash) sdhgfsajhdgfjsahgd end")
        self.assertStatusCode(resp, 400)

    def test_unicode_error(self):
        resp = self.request_lua(u"function main(splash) 'привет' end".encode('utf8'))
        self.assertStatusCode(resp, 400)
        self.assertIn("unexpected symbol", resp.text)

    def test_user_error(self):
        resp = self.request_lua("""
        function main(splash)
          error("User Error Happened")
        end
        """)
        self.assertStatusCode(resp, 400)
        self.assertIn("User Error Happened", resp.text)

    def test_bad_splash_attribute(self):
        resp = self.request_lua("""
        function main(splash)
          local x = splash.foo
          return x == nil
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "True")

    def test_return_multiple(self):
        resp = self.request_lua("function main(splash) return 'foo', 'bar' end")
        self.assertStatusCode(resp, 400)
        self.assertIn("must return a single result", resp.text)

    def test_return_splash(self):
        resp = self.request_lua("function main(splash) return splash end")
        self.assertStatusCode(resp, 400)

    def test_return_function(self):
        resp = self.request_lua("function main(splash) return function() end end")
        self.assertStatusCode(resp, 400)
        self.assertIn("functions are not allowed", resp.text)

    def test_return_coroutine(self):
        resp = self.request_lua("""
        function main(splash)
          return coroutine.create(function() end)
        end
        """)
        self.assertStatusCode(resp, 400)
        self.assertIn("functions are not allowed", resp.text)

    def test_return_started_coroutine(self):
        resp = self.request_lua("""
        function main(splash)
          local co = coroutine.create(function()
            coroutine.yield()
          end)
          coroutine.resume(co)
          return co
        end
        """)
        self.assertStatusCode(resp, 400)
        self.assertIn("coroutines are not allowed", resp.text)


class RunjsTest(BaseLuaRenderTest):

    def assertRunjsResult(self, js, result, type):
        resp = self.request_lua("""
        function main(splash)
            local res = splash:runjs([[%s]])
            return {res=res, tp=type(res)}
        end
        """ % js)
        self.assertStatusCode(resp, 200)
        if result is None:
            self.assertEqual(resp.json(), {'tp': type})
        else:
            self.assertEqual(resp.json(), {'res': result, 'tp': type})

    def test_numbers(self):
        self.assertRunjsResult("1.0", 1.0, "number")
        self.assertRunjsResult("1", 1, "number")
        self.assertRunjsResult("1+2", 3, "number")

    def test_string(self):
        self.assertRunjsResult("'foo'", u'foo', 'string')

    def test_bool(self):
        self.assertRunjsResult("true", True, 'boolean')

    def test_undefined(self):
        self.assertRunjsResult("undefined", None, 'nil')

    def test_null(self):
        # XXX: null is converted to an empty string by QT,
        # we can't distinguish it from a "real" empty string.
        self.assertRunjsResult("null", "", 'string')

    def test_unicode_string(self):
        self.assertRunjsResult("'привет'", u'привет', 'string')

    def test_unicode_string_in_object(self):
        self.assertRunjsResult(
            'var o={}; o["ключ"] = "значение"; o',
            {u'ключ': u'значение'},
            'table'
        )

    def test_nested_object(self):
        self.assertRunjsResult(
            'var o={}; o["x"] = {}; o["x"]["y"] = 5; o["z"] = "foo"; o',
            {"x": {"y": 5}, "z": "foo"},
            'table'
        )

    def test_array(self):
        self.assertRunjsResult(
            'x = [1, 2, 3, "foo", {}]; x',
            [1, 2, 3, "foo", {}],
            'userdata',  # XXX: it'be great for it to be 'table'
        )

    def test_self_referencing(self):
        self.assertRunjsResult(
            'var o={}; o["x"] = "5"; o["y"] = o; o',
            {"x": "5"},  # self reference is discarded
            'table'
        )

    def test_function(self):
        # XXX: complex objects are not returned by QT
        self.assertRunjsResult(
            "x = function(){return 5}; x",
            {},
            "table"
        )

        self.assertRunjsResult(
            "function(){return 5}",
            None,
            "nil"
        )

    def test_dateobj(self):
        # XXX: Date objects are converted to ISO8061 strings.
        # Does it make sense to do anything else with them?
        # E.g. make them available to Lua as tables?
        self.assertRunjsResult(
            'x = new Date("21 May 1958 10:12 UTC"); x',
            "1958-05-21T10:12:00Z",
            "string"
        )

    def test_regexp(self):
        self.assertRunjsResult(
            '/my-regexp/i',
            {
                u'_jstype': u'RegExp',
                'caseSensitive': False,
                'pattern': u'my-regexp'
            },
            'table'
        )

        self.assertRunjsResult(
            '/my-regexp/',
            {
                u'_jstype': u'RegExp',
                'caseSensitive': True,
                'pattern': u'my-regexp'
            },
            'table'
        )

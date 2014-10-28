# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest
import pytest

from splash.lua import get_script_source
from . import test_render, test_redirects, test_har
from .test_jsonpost import JsonPostRequestHandler
from .utils import NON_EXISTING_RESOLVABLE


class BaseLuaRenderTest(test_render.BaseRenderTest):
    render_format = 'lua'

    def request_lua(self, code, query=None):
        q = {"lua_source": code}
        q.update(query or {})
        return self.request(q)


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


class WaitTest(BaseLuaRenderTest):
    def test_timeout(self):
        code = """
        function main(splash)
          splash:wait(0.01)
        end
        """
        resp = self.request_lua(code, {"timeout": 0.1})
        self.assertStatusCode(resp, 200)

        code = """
        function main(splash)
          splash:wait(1)
        end
        """
        resp = self.request_lua(code, {"timeout": 0.1})
        self.assertStatusCode(resp, 504)

    def test_wait_success(self):
        resp = self.request_lua("""
        function main(splash)
          local ok, reason = splash:wait(0.01)
          return {ok=ok, reason=reason}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_wait_noredirect(self):
        resp = self.request_lua("""
        function main(splash)
          local ok, reason = splash:wait{time=0.01, cancel_on_redirect=true}
          return {ok=ok, reason=reason}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_wait_redirect_nocancel(self):
        # jsredirect-timer redirects after 0.1ms
        resp = self.request_lua("""
        function main(splash)
          assert(splash:go(splash.args.url))
          local ok, reason = splash:wait{time=0.2, cancel_on_redirect=false}
          return {ok=ok, reason=reason}
        end
        """, {'url': self.mockurl("jsredirect-timer")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_wait_redirect_cancel(self):
        # jsredirect-timer redirects after 0.1ms
        resp = self.request_lua("""
        function main(splash)
          assert(splash:go(splash.args.url))
          local ok, reason = splash:wait{time=0.2, cancel_on_redirect=true}
          return {ok=ok, reason=reason}
        end
        """, {'url': self.mockurl("jsredirect-timer")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"reason": "redirect"})  # ok is nil

    def test_wait_badarg(self):
        resp = self.request_lua("""
        function main(splash)
          splash:wait{time="sdf"}
        end
        """)
        self.assertStatusCode(resp, 400)

    def test_wait_noargs(self):
        resp = self.request_lua("""
        function main(splash)
          splash:wait()
        end
        """)
        self.assertStatusCode(resp, 400)

    def test_wait_negative(self):
        resp = self.request_lua("""
        function main(splash)
          splash:wait(-0.2)
        end
        """)
        self.assertStatusCode(resp, 400)


class ArgsTest(BaseLuaRenderTest):
    def args_request(self, query):
        func = """
        function main(splash)
          return {args=splash.args}
        end
        """
        return self.request_lua(func, query)

    def assertArgs(self, query):
        resp = self.args_request(query)
        self.assertStatusCode(resp, 200)
        data = resp.json()["args"]
        data.pop('lua_source')
        data.pop('uid')
        return data

    def assertArgsPassed(self, query):
        args = self.assertArgs(query)
        self.assertEqual(args, query)
        return args

    def test_known_args(self):
        self.assertArgsPassed({"wait": "1.0"})
        self.assertArgsPassed({"timeout": "2.0"})
        self.assertArgsPassed({"url": "foo"})

    def test_unknown_args(self):
        self.assertArgsPassed({"foo": "bar"})

    def test_filters_validation(self):
        # 'global' known arguments are still validated
        resp = self.args_request({"filters": 'foo,bar'})
        self.assertStatusCode(resp, 400)
        self.assertIn("Invalid filter names", resp.text)


class JsonPostArgsTest(ArgsTest):
    request_handler = JsonPostRequestHandler

    def test_headers(self):
        headers = {"user-agent": "Firefox", "content-type": "text/plain"}
        self.assertArgsPassed({"headers": headers})

    def test_headers_items(self):
        headers = [["user-agent", "Firefox"], ["content-type", "text/plain"]]
        self.assertArgsPassed({"headers": headers})

    def test_access_headers(self):
        func = """
        function main(splash)
          local ua = "Unknown"
          if splash.args.headers then
            ua = splash.args.headers['user-agent']
          end
          return {ua=ua, firefox=(ua=="Firefox")}
        end
        """
        resp = self.request_lua(func, {'headers': {"user-agent": "Firefox"}})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ua": "Firefox", "firefox": True})

        resp = self.request_lua(func)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ua": "Unknown", "firefox": False})

    def test_custom_object(self):
        self.assertArgsPassed({"myobj": {"foo": "bar", "bar": ["egg", "spam", 1]}})

    def test_post_numbers(self):
        self.assertArgsPassed({"x": 5})


class Base:
    # a hack to skip test running from a mixin
    class EmulationMixin(test_render.BaseRenderTest):
        render_format = 'lua'

        def request(self, query, render_format=None, headers=None, **kwargs):
            query = {} or query
            query.update({'lua_source': self.script})
            return self._get_handler().request(query, render_format, headers, **kwargs)

        def post(self, query, render_format=None, payload=None, headers=None, **kwargs):
            raise NotImplementedError()

        # ==== overridden tests =============================
        @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
        def test_render_error(self):
            r = self.request({"url": "http://non-existent-host/"})
            self.assertStatusCode(r, 400)

        def test_self(self):
            # make sure mixin order is correct
            assert self.render_format == 'lua'



class EmulatedRenderHtmlTest(Base.EmulationMixin, test_render.RenderHtmlTest):
    script = get_script_source("render_html.lua")


class EmulatedHttpRedirectTest(Base.EmulationMixin, test_redirects.HttpRedirectTest):
    script = get_script_source("render_html.lua")


class EmulatedJsRedirectTest(Base.EmulationMixin, test_redirects.JsRedirectTest):
    script = get_script_source("render_html.lua")

    # Overridden to return 400.
    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_redirect_to_non_existing(self):
        r = self.request({
            "url": self.mockurl("jsredirect-non-existing"),
            "wait": 0.2,
        })
        self.assertStatusCode(r, 400)


class EmulatedMetaRedirectTest(Base.EmulationMixin, test_redirects.MetaRedirectTest):
    script = get_script_source("render_html.lua")


class EmulatedRenderPngTest(Base.EmulationMixin, test_render.RenderPngTest):
    script = get_script_source("render_png.lua")

    # TODO: default width and height are not applied
    @pytest.mark.xfail
    def test_ok(self):
        super(EmulatedRenderPngTest, self).test_ok()

    @pytest.mark.xfail
    def test_ok_https(self):
        super(EmulatedRenderPngTest, self).test_ok_https()

    # TODO: fix validation
    @pytest.mark.xfail
    def test_viewport_out_of_bounds(self):
        super(EmulatedRenderPngTest, self).test_viewport_out_of_bounds()

    @pytest.mark.xfail
    def test_viewport_invalid(self):
        super(EmulatedRenderPngTest, self).test_viewport_invalid()

    @pytest.mark.xfail
    def test_range_checks(self):
        super(EmulatedRenderPngTest, self).test_range_checks()

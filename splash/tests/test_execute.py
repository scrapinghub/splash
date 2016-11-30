# -*- coding: utf-8 -*-
from __future__ import absolute_import

import base64
import unittest
from io import BytesIO
import numbers
import time

from PIL import Image
import requests
import six
import pytest

lupa = pytest.importorskip("lupa")

from splash.exceptions import ScriptError
from splash.qtutils import qt_551_plus
from splash import __version__ as splash_version
from splash.har_builder import HarBuilder
from splash.har.utils import get_response_body_bytes

from . import test_render
from .test_jsonpost import JsonPostRequestHandler
from .utils import NON_EXISTING_RESOLVABLE, SplashServer
from .mockserver import JsRender
from .. import defaults


class BaseLuaRenderTest(test_render.BaseRenderTest):
    endpoint = 'execute'

    def request_lua(self, code, query=None, **kwargs):
        q = {"lua_source": code}
        q.update(query or {})
        return self.request(q, **kwargs)

    def assertScriptError(self, resp, subtype, message=None):
        err = self.assertJsonError(resp, 400, 'ScriptError')
        self.assertEqual(err['info']['type'], subtype)
        if message is not None:
            self.assertRegexpMatches(err['info']['message'], message)
        return err

    def assertErrorLineNumber(self, resp, line_number):
        self.assertEqual(resp.json()['info']['line_number'], line_number)


class MainFunctionTest(BaseLuaRenderTest):
    def test_return_json(self):
        resp = self.request_lua("""
        function main(splash)
          local obj = {key="value"}
          return {
            mystatus="ok",
            number=5,
            float=-0.1,
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
            "float": -0.1,
            "obj": {"key": "value"},
            "bool": True,
            "bool2": False,
        })

    def test_unicode(self):
        resp = self.request_lua(u"""
        function main(splash) return {key="значение"} end
        """)

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.headers['content-type'], 'application/json')
        self.assertEqual(resp.json(), {"key": u"значение"})

    def test_unicode_direct(self):
        resp = self.request_lua(u"""
        function main(splash)
          return 'привет'
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, u"привет")
        self.assertEqual(resp.headers['content-type'], 'text/plain; charset=utf-8')

    def test_number(self):
        resp = self.request_lua("function main(splash) return 1 end")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "1")
        self.assertEqual(resp.headers['content-type'], 'text/plain; charset=utf-8')

    def test_number_float(self):
        resp = self.request_lua("function main(splash) return 1.5 end")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "1.5")
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

    def test_no_main(self):
        resp = self.request_lua("x=1")
        self.assertScriptError(resp, ScriptError.MAIN_NOT_FOUND_ERROR,
                               message="function is not found")

    def test_bad_main(self):
        resp = self.request_lua("main=1")
        self.assertScriptError(resp, ScriptError.BAD_MAIN_ERROR,
                               message="is not a function")

    def test_ugly_main(self):
        resp = self.request_lua("main={coroutine=123}")
        self.assertScriptError(resp, ScriptError.BAD_MAIN_ERROR,
                               message="is not a function")

    def test_nasty_main(self):
        resp = self.request_lua("""
        main = {coroutine=function()
          return {
            send=function() end,
            next=function() end
          }
        end}
        """)
        self.assertScriptError(resp, ScriptError.BAD_MAIN_ERROR,
                               message="is not a function")


class ResultContentTypeTest(BaseLuaRenderTest):
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

    def test_content_type_ignored_for_tables(self):
        resp = self.request_lua("""
        function main(splash)
          splash:set_result_content_type('text/plain')
          return {hi="hi!"}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.headers['content-type'], 'application/json')
        self.assertEqual(resp.text, '{"hi": "hi!"}')

    def test_bad_content_type(self):
        resp = self.request_lua("""
        function main(splash)
          splash:set_result_content_type(55)
          return "hi!"
        end
        """)
        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='argument must be a string')
        self.assertEqual(err['info']['splash_method'], 'set_result_content_type')

        resp = self.request_lua("""
        function main(splash)
          splash:set_result_content_type()
          return "hi!"
        end
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_bad_content_type_func(self):
        resp = self.request_lua("""
        function main(splash)
          splash:set_result_content_type(function () end)
          return "hi!"
        end
        """)
        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)
        self.assertEqual(err['info']['splash_method'], 'set_result_content_type')


class ResultHeaderTest(BaseLuaRenderTest):
    def test_result_header_set(self):
        resp = self.request_lua("""
        function main(splash)
            splash:set_result_header("foo", "bar")
            return "hi!"
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertIn("foo", resp.headers)
        self.assertEqual(resp.headers.get("foo"), "bar")

    def test_bad_result_header_set(self):
        resp = self.request_lua("""
        function main(splash)
            splash:set_result_header({}, {})
            return "hi!"
        end
        """)
        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='arguments must be strings')
        self.assertEqual(err['info']['splash_method'], 'set_result_header')
        self.assertErrorLineNumber(resp, 3)

    def test_unicode_headers_raise_bad_request(self):
        resp = self.request_lua(u"""
        function main(splash)
            splash:set_result_header("paweł", "kiść")
            return "hi!"
        end
        """)
        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='must be ascii')
        self.assertEqual(err['info']['splash_method'], 'set_result_header')
        self.assertErrorLineNumber(resp, 3)


class ErrorsTest(BaseLuaRenderTest):
    def test_syntax_error(self):
        resp = self.request_lua("function main(splash) sdhgfsajhdgfjsahgd end")
        # XXX: message='syntax error' is not checked because older Lua 5.2
        # versions have problems with error messages.
        self.assertScriptError(resp, ScriptError.LUA_INIT_ERROR)

    def test_syntax_error_toplevel(self):
        resp = self.request_lua("sdg; function main(splash) sdhgfsajhdgfjsahgd end")
        self.assertScriptError(resp, ScriptError.LUA_INIT_ERROR)
        # XXX: message='syntax error' is not checked because older Lua 5.2
        # versions have problems with error messages.

    def test_unicode_error(self):
        resp = self.request_lua(u"function main(splash) 'привет' end")
        self.assertScriptError(resp, ScriptError.LUA_INIT_ERROR,
                               message="unexpected symbol")

    def test_user_error(self):
        resp = self.request_lua("""     -- 1
        function main(splash)           -- 2
          error("User Error Happened")  -- 3  <-
        end
        """)
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message="User Error Happened")
        self.assertErrorLineNumber(resp, 3)

    @pytest.mark.xfail(reason="not implemented, nice to have")
    def test_user_error_table(self):
        resp = self.request_lua("""           -- 1
        function main(splash)                 -- 2
          error({tp="user error", msg=123})   -- 3  <-
        end
        """)
        err = self.assertScriptError(resp, ScriptError.LUA_ERROR)
        self.assertEqual(err['info']['error'],
                         {'tp': 'user error', 'msg': 123})
        self.assertErrorLineNumber(resp, 3)

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
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), ["foo", "bar"])

    def test_return_splash(self):
        resp = self.request_lua("function main(splash) return splash end")
        self.assertScriptError(resp, ScriptError.BAD_MAIN_ERROR)

    def test_return_function(self):
        resp = self.request_lua("function main(s) return function() end end")
        self.assertScriptError(resp, ScriptError.BAD_MAIN_ERROR,
                               message="function objects are not allowed")

    def test_return_coroutine(self):
        resp = self.request_lua("""
        function main(splash)
          return coroutine.create(function() end)
        end
        """)
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message="(a nil value)")

    def test_return_coroutine_nosandbox(self):
        with SplashServer(extra_args=['--disable-lua-sandbox']) as splash:
            resp = requests.get(
                url=splash.url("execute"),
                params={
                    'lua_source': """
                        function main(splash)
                            return coroutine.create(function() end)
                        end
                    """
                },
            )
            self.assertScriptError(resp, ScriptError.BAD_MAIN_ERROR,
                                   message="function objects are not allowed")

    def test_return_started_coroutine(self):
        resp = self.request_lua("""               -- 1
        function main(splash)                     -- 2
          local co = coroutine.create(function()  -- 3  <-
            coroutine.yield()                     -- 4
          end)
          coroutine.resume(co)
          return co
        end
        """)
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message="(a nil value)")
        self.assertErrorLineNumber(resp, 3)

    def test_return_started_coroutine_nosandbox(self):
        with SplashServer(extra_args=['--disable-lua-sandbox']) as splash:
            resp = requests.get(
                url=splash.url("execute"),
                params={
                    'lua_source': """                            -- 1
                        function main(splash)                    -- 2
                          local co = coroutine.create(function() -- 3
                            coroutine.yield()                    -- 4
                          end)                                   -- 5
                          coroutine.resume(co)                   -- 6
                          return co                              -- 7
                        end                                      -- 8
                    """
                },
            )
            self.assertScriptError(resp, ScriptError.BAD_MAIN_ERROR,
                                   message="thread objects are not allowed")

    def test_error_line_number_attribute_access(self):
        resp = self.request_lua("""                -- 1
        function main(splash)                      -- 2
           local x = 5                             -- 3
           splash.set_result_content_type("hello") -- 4
        end                                        -- 5
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)
        self.assertErrorLineNumber(resp, 4)

    def test_error_line_number_bad_argument(self):
        resp = self.request_lua("""
        function main(splash)
           local x = 5
           splash:set_result_content_type(48)
        end
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)
        self.assertErrorLineNumber(resp, 4)

    def test_error_line_number_wrong_keyword_argument(self):
        resp = self.request_lua("""                         -- 1
        function main(splash)                               -- 2
           splash:set_result_content_type{content_type=48}  -- 3  <--
        end                                                 -- 4
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)
        self.assertErrorLineNumber(resp, 3)

    def test_pcall_wrong_keyword_arguments(self):
        resp = self.request_lua("""
        function main(splash)
           local x = function()
               return splash:wait{timeout=0.7}
           end
           local ok, res = pcall(x)
           return {ok=ok, res=res}
        end
        """)
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data["ok"], False)


class EnableDisableJSTest(BaseLuaRenderTest):
    def test_disablejs(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash.js_enabled==true)
            splash.js_enabled = false
            splash:go(splash.args.url)
            local html = splash:html()
            return html
        end
        """, {
            'url': self.mockurl('jsrender'),
        })
        self.assertStatusCode(resp, 200)
        self.assertIn(u'Before', resp.text)

    def test_enablejs(self):
        resp = self.request_lua("""
        function main(splash)
            splash.js_enabled = true
            splash:go(splash.args.url)
            local html = splash:html()
            return html
        end
        """, {
            'url': self.mockurl('jsrender'),
        })
        self.assertStatusCode(resp, 200)
        self.assertNotIn(u'Before', resp.text)

    def test_disablejs_after_splash_go(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash.js_enabled = false
            local html = splash:html()
            return html
        end
        """, {
            'url': self.mockurl('jsrender'),
        })
        self.assertStatusCode(resp, 200)
        self.assertNotIn(u'Before', resp.text)

    def test_multiple(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash.js_enabled = false
            local html_1 = splash:html()
            splash:go(splash.args.url)
            return {html_1=html_1, html_2=splash:html()}
        end
        """, {
            'url': self.mockurl('jsrender')
        })
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertNotIn(u'Before', data['html_1'])
        self.assertIn(u'Before', data['html_2'])


class ImageRenderTest(BaseLuaRenderTest):
    def test_disable_images_attr(self):
        resp = self.request_lua("""
        function main(splash)
            splash.images_enabled = false
            splash:go(splash.args.url)
            local res = splash:evaljs("document.getElementById('foo').clientHeight")
            return {res=res}
        end
        """, {'url': self.mockurl("show-image")})
        self.assertEqual(resp.json()['res'], 0)

    def test_disable_images_method(self):
        resp = self.request_lua("""
        function main(splash)
            splash:set_images_enabled(false)
            splash:go(splash.args.url)
            local res = splash:evaljs("document.getElementById('foo').clientHeight")
            return {res=res}
        end
        """, {'url': self.mockurl("show-image")})
        self.assertEqual(resp.json()['res'], 0)

    def test_enable_images_attr(self):
        resp = self.request_lua("""
        function main(splash)
            splash.images_enabled = false
            splash.images_enabled = true
            splash:go(splash.args.url)
            local res = splash:evaljs("document.getElementById('foo').clientHeight")
            return {res=res}
        end
        """, {'url': self.mockurl("show-image")})
        self.assertEqual(resp.json()['res'], 50)

    def test_enable_images_method(self):
        resp = self.request_lua("""
        function main(splash)
            splash:set_images_enabled(false)
            splash:set_images_enabled(true)
            splash:go(splash.args.url)
            local res = splash:evaljs("document.getElementById('foo').clientHeight")
            return {res=res}
        end
        """, {'url': self.mockurl("show-image")})
        self.assertEqual(resp.json()['res'], 50)


class EvaljsTest(BaseLuaRenderTest):
    def _evaljs_request(self, js):
        return self.request_lua("""
        function main(splash)
            local res = splash:evaljs([[%s]])
            return {res=res, tp=type(res)}
        end
        """ % js)

    def assertEvaljsResult(self, js, result, type):
        resp = self._evaljs_request(js)
        self.assertStatusCode(resp, 200)
        expected = {'tp': type}
        if result is not None:
            expected['res'] = result
        self.assertEqual(resp.json(), expected)

    def assertEvaljsError(self, js, subtype=ScriptError.JS_ERROR, message=None):
        resp = self._evaljs_request(js)
        err = self.assertScriptError(resp, subtype, message)
        self.assertEqual(err['info']['splash_method'], 'evaljs')
        return err

    def test_numbers(self):
        self.assertEvaljsResult("1.0", 1.0, "number")
        self.assertEvaljsResult("1", 1, "number")
        self.assertEvaljsResult("1+2", 3, "number")

    def test_inf(self):
        self.assertEvaljsResult("1/0", float('inf'), "number")
        self.assertEvaljsResult("-1/0", float('-inf'), "number")

    def test_string(self):
        self.assertEvaljsResult("'foo'", u'foo', 'string')

    def test_bool(self):
        self.assertEvaljsResult("true", True, 'boolean')

    def test_array(self):
        self.assertEvaljsResult("var a = [1, 2, 'x']; a",
                                [1, 2, 'x'], 'table')

    def test_array_nested(self):
        self.assertEvaljsResult("var a = [1, 2, 'x', {x: 5, y: [2, [], 1]}]; a",
                                [1, 2, 'x', {'x': 5, 'y': [2, [], 1]}], 'table')

    def test_object_nested(self):
        self.assertEvaljsResult("var x = {x: [1, 2, 'x', {y: 5}]}; x",
                                {'x': [1, 2, 'x', {'y': 5}]}, 'table')

    def test_undefined(self):
        self.assertEvaljsResult("undefined", None, 'nil')

    def test_null(self):
        # XXX: null is converted to an empty string by QT,
        # we can't distinguish it from a "real" empty string.
        self.assertEvaljsResult("null", "", 'string')

    def test_unicode_string(self):
        self.assertEvaljsResult("'привет'", u'привет', 'string')

    def test_unicode_string_in_object(self):
        self.assertEvaljsResult(
            'var o={}; o["ключ"] = "значение"; o',
            {u'ключ': u'значение'},
            'table'
        )

    def test_nested_object(self):
        self.assertEvaljsResult(
            'var o={}; o["x"] = {}; o["x"]["y"] = 5; o["z"] = "foo"; o',
            {"x": {"y": 5}, "z": "foo"},
            'table'
        )

    def test_array(self):
        self.assertEvaljsResult(
            'x = [3, 2, 1, "foo", ["foo", [], "bar"], {}]; x',
            [3, 2, 1, "foo", ["foo", [], "bar"], {}],
            'table',
        )

    def test_self_referencing(self):
        self.assertEvaljsError(
            'var o={}; o["x"] = "5"; o["y"] = o; o',
            message="Object is too deep or recursive"
        )

    def test_JSON_overridden(self):
        self.assertEvaljsResult("window.JSON = {}; 'hello'", 'hello', 'string')

    def test_function(self):
        # XXX: functions are not returned by QT
        self.assertEvaljsResult("x = function(){return 5}; x", None, "nil")

    def test_html_element(self):
        resp = self.request_lua("""
        function main(splash)
           local div = splash:evaljs("document.createElement('div')")
           return div.node.nodeName:lower()
        end
        """)

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'div')

    def test_host_object_xhr(self):
        self.assertEvaljsResult("(new XMLHttpRequest())", None, "nil")

    def test_function_direct_unwrapped(self):
        # XXX: this is invaild syntax
        self.assertEvaljsError("function(){return 5}", message='SyntaxError')

    def test_function_direct(self):
        self.assertEvaljsResult("(function(){return 5})", None, "nil")

    def test_object_with_function(self):
        # XXX: complex objects like function values are unsupported
        self.assertEvaljsResult('var o = {x:2, y: (function(){})}; o',
                                {"x": 2}, "table")

    def test_function_call(self):
        self.assertEvaljsResult(
            "function x(){return 5}; x();",
            5,
            "number"
        )

    def test_dateobj(self):
        # XXX: Date objects are converted to ISO8061 strings.
        # Does it make sense to do anything else with them?
        # E.g. make them available to Lua as tables?
        self.assertEvaljsResult(
            'x = new Date("21 May 1958 10:12 UTC"); x',
            "1958-05-21T10:12:00.000Z",
            "string"
        )

    def test_syntax_error(self):
        err = self.assertEvaljsError("x--4")
        self.assertEqual(err['info']['js_error_type'], 'SyntaxError')

    def test_throw_string(self):
        err = self.assertEvaljsError("(function(){throw 'ABC'})();")
        self.assertEqual(err['info']['js_error_type'], '<custom JS error>')
        self.assertEqual(err['info']['js_error_message'], 'ABC')

        err = self.assertEvaljsError("throw 'ABC'")
        self.assertEqual(err['info']['js_error_type'], '<custom JS error>')
        self.assertEqual(err['info']['js_error_message'], 'ABC')

    def test_throw_error(self):
        err = self.assertEvaljsError("(function(){throw new Error('ABC')})();")
        self.assertEqual(err['info']['js_error_type'], 'Error')
        self.assertEqual(err['info']['js_error_message'], 'ABC')


class WaitForResumeTest(BaseLuaRenderTest):
    maxDiff = 2000

    def _wait_for_resume_request(self, js, timeout=1.0):
        return self.request_lua("""
        function main(splash)
            local result, error = splash:wait_for_resume([[%s]], %.1f)
            local response = {}

            if result ~= nil then
                response["value"] = result["value"]
                response["value_type"] = type(result["value"])
            else
                response["error"] = error
            end

            return response
        end
        """ % (js, timeout))

    def test_return_undefined(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume();
            }
        """)
        self.assertStatusCode(resp, 200)
        # A Lua table with a nil value is equivalent to not setting that
        # key/value pair at all, so there is no "result" key in the response.
        self.assertEqual(resp.json(), {"value_type": "nil"})

    def test_return_null(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume(null);
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"value": "", "value_type": "string"})

    def test_return_string(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume("ok");
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"value": "ok", "value_type": "string"})

    def test_return_non_ascii_string(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume("你好");
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"value": u"你好", "value_type": "string"})

    def test_return_int(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume(42);
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"value": 42, "value_type": "number"})

    def test_return_float(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume(1234.5);
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"value": 1234.5, "value_type": "number"})

    def test_return_boolean(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume(true);
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"value": True, "value_type": "boolean"})

    def test_return_list(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume([1,2,'red','blue']);
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            "value": [1, 2, 'red', 'blue'],
            "value_type": "table",
        })

    def test_return_dict(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume({'stomach':'empty','brain':'crazy'});
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            "value": {'stomach': 'empty', 'brain': 'crazy'},
            "value_type": "table",
        })

    def test_return_host_object_document(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume(document);
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'value_type': 'nil'})

    def test_return_host_object_xhr(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                var xhr = new XMLHttpRequest();
                splash.resume(xhr);
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'value_type': 'nil'})

    def test_return_dict_circular(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                var dct = {'hello': 'world'};
                dct['me'] = dct;
                splash.resume(dct);
            }
        """)
        err = self.assertJsonError(resp, 400, 'ScriptError')
        self.assertIn('Object is too deep or recursive', err['info']['error'])

    def test_return_additional_keys(self):
        resp = self.request_lua("""
        function main(splash)
            local result, error = splash:wait_for_resume([[
                function main(splash) {
                    splash.set("foo", "bar");
                    splash.resume("ok");
                }
            ]])

            return result
        end""")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'foo': 'bar', 'value': 'ok'})

    def test_delayed_return(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                setTimeout(function () {
                    splash.resume("ok");
                }, 100);
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"value": "ok", "value_type": "string"})

    def test_error_string(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.error("not ok");
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"error": "JavaScript error: not ok"})

    def test_timed_out(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                setTimeout(function () {
                    splash.resume("ok");
                }, 2500);
            }
        """, timeout=0.1)
        expected_error = 'JavaScript error: One shot callback timed out' \
                         ' while waiting for resume() or error().'
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"error": expected_error})

    def test_missing_main_function(self):
        resp = self._wait_for_resume_request("""
            function foo(splash) {
                setTimeout(function () {
                    splash.resume("ok");
                }, 500);
            }
        """)
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message=r"no main\(\) function defined")

    def test_js_syntax_error(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                )
                setTimeout(function () {
                    splash.resume("ok");
                }, 500);
            }
        """)
        # XXX: why is it LUA_ERROR, not JS_ERROR? Should we change that?
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message="SyntaxError")

    def test_js_error(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume(foo);  // foo is not defined
            }
        """)
        err = self.assertJsonError(resp, 400, 'ScriptError')
        self.assertIn("ReferenceError: Can't find variable: foo",
                      err['info']['error'])

    def test_js_error_custom(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                throw Error("oops!")
            }
        """)
        err = self.assertJsonError(resp, 400, 'ScriptError')
        self.assertIn('Error: oops!', err['info']['error'])

    def test_js_error_circular(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                var err = Error("oops!");
                err.e = err;
                throw err
            }
        """)
        err = self.assertJsonError(resp, 400, 'ScriptError')
        self.assertIn('Error: oops!', err['info']['error'])

    def test_js_error_circular_object(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                var err = {'msg': 'oops!'};
                err['me'] = err;
                throw err
            }
        """)
        err = self.assertJsonError(resp, 400, 'ScriptError')
        self.assertEqual(err['info']['error'],
                         "JavaScript error: [object Object]")

    def test_navigation_cancels_resume(self):
        resp = self._wait_for_resume_request("""
            function main(splash) {
                location.href = '%s';
            }
        """ % self.mockurl('/'))
        json = resp.json()
        self.assertStatusCode(resp, 200)
        self.assertIn('error', json)
        self.assertIn('canceled', json['error'])

    def test_cannot_resume_twice(self):
        """
        We can't easily test that resuming twice throws an exception,
        because that exception is thrown in Python code after Lua has already
        resumed. The server log (if set to verbose) will show the stack trace,
        but Lua will have no idea that it happened; indeed, that's the
        _whole purpose_ of the one shot callback.

        We can at least verify that if resume is called multiple times,
        then the first value is returned and subsequent values are ignored.
        """

        resp = self._wait_for_resume_request("""
            function main(splash) {
                splash.resume('ok');
                setTimeout(function () {
                    splash.resume('not ok');
                }, 500);
            }
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"value": "ok", "value_type": "string"})


class RunjsTest(BaseLuaRenderTest):
    def test_define_variable(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:runjs("x=5"))
            return {x=splash:evaljs("x")}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"x": 5})

    def test_runjs_undefined(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:runjs("undefined"))
            return {ok=true}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_define_function(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:runjs("egg = function(){return 'spam'};"))
            local egg = splash:jsfunc("window.egg")
            return {egg=egg()}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"egg": "spam"})

    def test_runjs_syntax_error(self):
        resp = self.request_lua("""
        function main(splash)
            local res, err = splash:runjs("function()")
            return {res=res, err=err}
        end
        """)
        self.assertStatusCode(resp, 200)
        err = resp.json()['err']
        self.assertEqual(err['type'], ScriptError.JS_ERROR)
        self.assertEqual(err['js_error_type'], 'SyntaxError')
        self.assertEqual(err['splash_method'], 'runjs')

    def test_runjs_exception(self):
        resp = self.request_lua("""
        function main(splash)
            local res, err = splash:runjs("var x = y;")
            return {res=res, err=err}
        end
        """)
        self.assertStatusCode(resp, 200)
        err = resp.json()['err']
        self.assertEqual(err['type'], ScriptError.JS_ERROR)
        self.assertEqual(err['js_error_type'], 'ReferenceError')
        self.assertRegexpMatches(err['message'], "Can't find variable")
        self.assertEqual(err['splash_method'], 'runjs')


class JsfuncTest(BaseLuaRenderTest):
    def assertJsfuncResult(self, source, arguments, result):
        resp = self.request_lua("""
        function main(splash)
            local func = splash:jsfunc([[%s]])
            return func(%s)
        end
        """ % (source, arguments))
        self.assertStatusCode(resp, 200)
        if isinstance(result, (dict, list)):
            self.assertEqual(resp.json(), result)
        else:
            self.assertEqual(resp.text, result)

    def test_Math(self):
        self.assertJsfuncResult("Math.pow", "5, 2", "25")

    def test_helloworld(self):
        self.assertJsfuncResult(
            "function(s) {return 'Hello, ' + s;}",
            "'world!'",
            "Hello, world!"
        )

    def test_object_argument(self):
        self.assertJsfuncResult(
            "function(obj) {return obj.foo;}",
            "{foo='bar'}",
            "bar",
        )

    def test_object_result(self):
        self.assertJsfuncResult(
            "function(obj) {return obj.foo;}",
            "{foo={x=5, y=10}}",
            {"x": 5, "y": 10},
        )

    def test_object_result_pass(self):
        resp = self.request_lua("""
        function main(splash)
            local func1 = splash:jsfunc("function(){return {foo:{x:5}}}")
            local func2 = splash:jsfunc("function(obj){return obj.foo}")
            local obj = func1()
            return func2(obj)
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"x": 5})

    def test_bool(self):
        is5 = "function(num){return num==5}"
        self.assertJsfuncResult(is5, "5", "True")
        self.assertJsfuncResult(is5, "6", "False")

    def test_undefined_result(self):
        self.assertJsfuncResult("function(){}", "", "None")

    def test_undefined_argument(self):
        self.assertJsfuncResult("function(foo){return foo}", "", "None")

    def test_throw_string(self):
        resp = self.request_lua("""
        function main(splash)
            local func = splash:jsfunc("function(){throw 'ABC'}")
            return func()
        end
        """)
        err = self.assertScriptError(resp, ScriptError.JS_ERROR)
        self.assertEqual(err['info']['js_error_message'], 'ABC')
        self.assertEqual(err['info']['js_error_type'], '<custom JS error>')

    def test_throw_pcall(self):
        resp = self.request_lua("""
        function main(splash)
            local func = splash:jsfunc("function(){throw 'ABC'}")
            local ok, res = pcall(func)
            return {ok=ok, res=res}
        end
        """)
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data["ok"], False)
        if six.PY3:
            self.assertIn("error during JS function call: 'ABC'", data[u"res"])
        else:
            self.assertIn("error during JS function call: u'ABC'", data[u"res"])

    def test_throw_error(self):
        resp = self.request_lua("""
        function main(splash)
            local func = splash:jsfunc("function(){throw new Error('ABC')}")
            return func()
        end
        """)
        err = self.assertScriptError(resp, ScriptError.JS_ERROR)
        self.assertEqual(err['info']['js_error_message'], 'ABC')
        self.assertEqual(err['info']['js_error_type'], 'Error')

    def test_throw_error_empty(self):
        resp = self.request_lua("""
        function main(splash)
            local func = splash:jsfunc("function(){throw new Error()}")
            return func()
        end
        """)
        err = self.assertScriptError(resp, ScriptError.JS_ERROR)
        self.assertEqual(err['info']['js_error_message'], '')
        self.assertEqual(err['info']['js_error_type'], 'Error')

    def test_throw_error_pcall(self):
        resp = self.request_lua("""
        function main(splash)
            local func = splash:jsfunc("function(){throw new Error('ABC')}")
            local ok, res = pcall(func)
            return {ok=ok, res=res}
        end
        """)
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data["ok"], False)
        if six.PY3:
            self.assertIn("error during JS function call: 'Error: ABC'", data[u"res"])
        else:
            self.assertIn("error during JS function call: u'Error: ABC'", data[u"res"])

    def test_js_syntax_error(self):
        resp = self.request_lua("""
        function main(splash)
            local func = splash:jsfunc("function(){")
            return func()
        end
        """)
        err = self.assertScriptError(resp, ScriptError.JS_ERROR)
        self.assertEqual(err['info']['js_error_type'], 'SyntaxError')

    def test_js_syntax_error_brace(self):
        resp = self.request_lua("""
        function main(splash)
            local func = splash:jsfunc('); window.alert("hello")')
            return func()
        end
        """)
        err = self.assertScriptError(resp, ScriptError.JS_ERROR)
        self.assertEqual(err['info']['js_error_type'], 'SyntaxError')

    def test_array_result(self):
        self.assertJsfuncResult(
            "function(){return [1, 2, 'foo']}",
            "",
            [1, 2, "foo"]
        )

    def test_array_result_processed(self):
        # XXX: note that index is started from 1
        resp = self.request_lua("""
        function main(splash)
            local func = splash:jsfunc("function(){return [1, 2, 'foo']}")
            local arr = func()
            local first = arr[1]
            return {arr=arr, first=1, tp=type(arr)}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"arr": [1, 2, "foo"], "first": 1, "tp": "table"})

    def test_array_argument(self):
        # XXX: note that index is started from 1
        self.assertJsfuncResult(
            "function(arr){return arr[1]}",
            "{5, 6, 'foo'}",
            "5",
        )

    def test_array_length(self):
        resp = self.request_lua("""
        treat = require("treat")
        function main(splash)
            local len = splash:jsfunc("function(arr){return arr.length}")
            local tbl = {5, 6, 'foo'}
            return len(treat.as_array(tbl))
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), 3)

    def test_jsfunc_attributes(self):
        resp = self.request_lua("""                                 -- 1
        function main(splash)                                       -- 2
            local func = splash:jsfunc("function(){return 123}")    -- 3
            return func.source                                      -- 4  <-
        end
        """)
        err = self.assertScriptError(resp, ScriptError.LUA_ERROR,
                                     message="attempt to index")
        self.assertEqual(err['info']['line_number'], 4)

    def test_private_jsfunc_not_available(self):
        resp = self.request_lua("""
        function main(splash)
            return {ok = splash._jsfunc == nil}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json()[u'ok'], True)

    def test_private_jsfunc_attributes(self):
        resp = self.request_lua("""                               -- 1
        function main(splash)                                     -- 2
            local func = splash:_jsfunc("function(){return 123}") -- 3 <-
            return func.source                                    -- 4
        end
        """)
        err = self.assertScriptError(resp, ScriptError.LUA_ERROR)
        self.assertEqual(err['info']['line_number'], 3)

    def test_html_element(self):
        resp = self.request_lua("""
        treat = require("treat")
        function main(splash)
            local create_el = splash:jsfunc("function(type){return document.createElement(type)}")
            return create_el('div').node.nodeName:lower();
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'div')

    def test_element_as_argument(self):
        resp = self.request_lua("""
        treat = require("treat")
        function main(splash)
            local div = splash:evaljs('document.createElement("div")')
            local get_node_name = splash:jsfunc("function(node){return node.nodeName.toLowerCase(); }")
            return get_node_name(div)
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'div')


class WaitTest(BaseLuaRenderTest):
    def wait(self, wait_args, request_args=None):
        code = """
        function main(splash)
          local ok, reason = splash:wait%s
          return {ok=ok, reason=reason}
        end
        """ % wait_args
        return self.request_lua(code, request_args)

    def go_and_wait(self, wait_args, request_args):
        code = """
        function main(splash)
          assert(splash:go(splash.args.url))
          local ok, reason = splash:wait%s
          return {ok=ok, reason=reason}
        end
        """ % wait_args
        return self.request_lua(code, request_args)

    def test_timeout(self):
        resp = self.wait("(0.01)", {"timeout": 0.1})
        self.assertStatusCode(resp, 200)

        resp = self.wait("(1)", {"timeout": 0.1})
        err = self.assertJsonError(resp, 504, "GlobalTimeoutError")
        self.assertEqual(err['info']['timeout'], 0.1)

    def test_wait_success(self):
        resp = self.wait("(0.01)")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_wait_noredirect(self):
        resp = self.wait("{time=0.01, cancel_on_redirect=true}")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_wait_redirect_nocancel(self):
        # jsredirect-timer redirects after 0.1ms
        resp = self.go_and_wait(
            "{time=0.2, cancel_on_redirect=false}",
            {'url': self.mockurl("jsredirect-timer")}
        )
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_wait_redirect_cancel(self):
        # jsredirect-timer redirects after 0.1ms
        resp = self.go_and_wait(
            "{time=0.2, cancel_on_redirect=true}",
            {'url': self.mockurl("jsredirect-timer")}
        )
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"reason": "redirect"})  # ok is nil

    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_wait_onerror(self):
        resp = self.go_and_wait(
            "{time=2., cancel_on_redirect=false, cancel_on_error=true}",
            {'url': self.mockurl("jsredirect-non-existing")}
        )
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"reason": "network3"})  # ok is nil

    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_wait_onerror_nocancel(self):
        resp = self.go_and_wait(
            "{time=2., cancel_on_redirect=false, cancel_on_error=false}",
            {'url': self.mockurl("jsredirect-non-existing")}
        )
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_wait_onerror_nocancel_redirect(self):
        resp = self.go_and_wait(
            "{time=2., cancel_on_redirect=true, cancel_on_error=false}",
            {'url': self.mockurl("jsredirect-non-existing")}
        )
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"reason": "redirect"})

    def test_wait_badarg(self):
        resp = self.wait('{time="sdf"}')
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_wait_badarg2(self):
        resp = self.wait('{time="sdf"}')
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_wait_good_string(self):
        resp = self.wait('{time="0.01"}')
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_wait_noargs(self):
        resp = self.wait('()')
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_wait_time_missing(self):
        resp = self.wait('{cancel_on_redirect=false}')
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_wait_unknown_args(self):
        resp = self.wait('{ttime=0.5}')
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_wait_negative(self):
        resp = self.wait('(-0.2)')
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)


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
        err = self.assertJsonError(resp, 400, "BadOption")
        self.assertEqual(err['info']['argument'], 'filters')


class JsonPostUnicodeTest(BaseLuaRenderTest):
    request_handler = JsonPostRequestHandler

    def test_unicode(self):
        resp = self.request_lua(u"""
        function main(splash) return {key="значение"} end
        """)

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.headers['content-type'], 'application/json')
        self.assertEqual(resp.json(), {"key": u"значение"})


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


class GoTest(BaseLuaRenderTest):
    def go_status(self, url):
        resp = self.request_lua("""
        function main(splash)
            local ok, reason = splash:go(splash.args.url)
            return {ok=ok, reason=reason}
        end
        """, {"url": url})
        self.assertStatusCode(resp, 200)
        return resp.json()

    def _geturl(self, code, empty=False):
        if empty:
            path = "getrequest?code=%s&empty=1" % code
        else:
            path = "getrequest?code=%s" % code
        return self.mockurl(path)

    def assertGoStatusCodeError(self, code):
        for empty in [False, True]:
            data = self.go_status(self._geturl(code, empty))
            self.assertNotIn("ok", data)
            self.assertEqual(data["reason"], "http%s" % code)

    def assertGoNoError(self, code):
        for empty in [False, True]:
            data = self.go_status(self._geturl(code, empty))
            self.assertTrue(data["ok"])
            self.assertNotIn("reason", data)

    def test_go_200(self):
        self.assertGoNoError(200)

    def test_go_400(self):
        self.assertGoStatusCodeError(400)

    def test_go_401(self):
        self.assertGoStatusCodeError(401)

    def test_go_403(self):
        self.assertGoStatusCodeError(403)

    def test_go_404(self):
        self.assertGoStatusCodeError(404)

    def test_go_500(self):
        self.assertGoStatusCodeError(500)

    def test_go_503(self):
        self.assertGoStatusCodeError(503)

    def test_nourl(self):
        resp = self.request_lua("function main(splash) splash:go() end")
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_nourl_args(self):
        resp = self.request_lua("function main(splash) splash:go(splash.args.url) end")
        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message="required")
        self.assertEqual(err['info']['argument'], 'url')

    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_go_error(self):
        data = self.go_status("non-existing")
        self.assertEqual(data.get('ok', False), False)
        self.assertEqual(data["reason"], "network301")

    def test_go_multiple(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url_1)
            local html_1 = splash:html()
            splash:go(splash.args.url_2)
            return {html_1=html_1, html_2=splash:html()}
        end
        """, {
            'url_1': self.mockurl('getrequest?foo=1'),
            'url_2': self.mockurl('getrequest?bar=2')
        })
        self.assertStatusCode(resp, 200)
        data = resp.json()
        if six.PY3:
            self.assertIn("{b'foo': [b'1']}", data['html_1'])
            self.assertIn("{b'bar': [b'2']}", data['html_2'])
        else:
            self.assertIn("{'foo': ['1']}", data['html_1'])
            self.assertIn("{'bar': ['2']}", data['html_2'])

    def test_go_404_then_good(self):
        resp = self.request_lua("""
        function main(splash)
            local ok1, err1 = splash:go(splash.args.url_1)
            local html_1 = splash:html()
            local ok2, err2 = splash:go(splash.args.url_2)
            local html_2 = splash:html()
            return {html_1=html_1, html_2=html_2, err1=err1, err2=err2, ok1=ok1, ok2=ok2}
        end
        """, {
            'url_1': self.mockurl('--some-non-existing-resource--'),
            'url_2': self.mockurl('bad-related'),
        })
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data["err1"], "http404")
        self.assertNotIn("err2", data)

        self.assertNotIn("ok1", data)
        self.assertEqual(data["ok2"], True)

        self.assertIn("No Such Resource", data["html_1"])
        self.assertIn("http://non-existing", data["html_2"])

    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_go_bad_then_good(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go("--non-existing-host")
            local ok, err = splash:go(splash.args.url)
            return {ok=ok, err=err}
        end
        """, {"url": self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_go_headers_cookie(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go{splash.args.url, headers={
                ["Cookie"] = "foo=bar; egg=spam"
            }})
            return splash:html()
        end
        """, {"url": self.mockurl("get-cookie?key=egg")})
        self.assertStatusCode(resp, 200)
        self.assertIn("spam", resp.text)

    def test_go_headers(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go{splash.args.url, headers={
                ["Custom-Header"] = "Header Value",
            }})
            local res1 = splash:html()

            -- second request is without any custom headers
            assert(splash:go(splash.args.url))
            local res2 = splash:html()

            return {res1=res1, res2=res2}
        end
        """, {"url": self.mockurl("getrequest")})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertIn("'Header Value'", data["res1"])
        self.assertNotIn("'Header Value'", data["res2"])

    def test_set_custom_headers(self):
        resp = self.request_lua("""
        function main(splash)
            splash:set_custom_headers({
                ["Header-1"] = "Value 1",
                ["Header-2"] = "Value 2",
            })

            assert(splash:go(splash.args.url))
            local res1 = splash:html()

            assert(splash:go{splash.args.url, headers={
                ["Header-3"] = "Value 3",
            }})
            local res2 = splash:html()

            assert(splash:go(splash.args.url))
            local res3 = splash:html()

            return {res1=res1, res2=res2, res3=res3}
        end
        """, {"url": self.mockurl("getrequest")})
        self.assertStatusCode(resp, 200)
        data = resp.json()

        self.assertIn("'Value 1'", data["res1"])
        self.assertIn("'Value 2'", data["res1"])
        self.assertNotIn("'Value 3'", data["res1"])

        self.assertNotIn("'Value 1'", data["res2"])
        self.assertNotIn("'Value 2'", data["res2"])
        self.assertIn("'Value 3'", data["res2"])

        self.assertIn("'Value 1'", data["res3"])
        self.assertIn("'Value 2'", data["res3"])
        self.assertNotIn("'Value 3'", data["res3"])

    def test_splash_go_POST(self):
        resp = self.request_lua("""
        function main(splash)
          formdata = {param1="foo", param2="bar"}
          ok, reason = assert(splash:go{splash.args.url, http_method="POST", formdata=formdata})
          return splash:html()
        end
        """, {"url": self.mockurl('postrequest')})
        self.assertStatusCode(resp, 200)
        self.assertTrue(
            "param2=bar&amp;param1=foo" in resp.text or
            "param1=foo&amp;param2=bar" in resp.text
            , resp.text)
        self.assertIn("application/x-www-form-urlencoded", resp.text)

    def test_splash_go_body_and_invalid_method(self):
        resp = self.request_lua("""
        function main(splash)
          ok, reason = splash:go{splash.args.url, http_method="GET", body="something",
                                 baseurl="foo"}
          return splash:html()
        end
        """, {"url": self.mockurl('postrequest')})
        self.assertStatusCode(resp, 400)
        self.assertIn('GET request cannot have body', resp.text)

    def test_splash_POST_json(self):
        json_payload = '{"name": "Frank", "address": "Elmwood Avenue 112"}'
        resp = self.request_lua("""
            function main(splash)
              headers = {}
              headers["content-type"] =  "application/json"
              ok, reason = assert(splash:go{splash.args.url, http_method="POST",
                                     body='%s',
                                     headers=headers})
              return splash:html()
            end
        """ % json_payload, {"url": self.mockurl('postrequest')})

        self.assertStatusCode(resp, 200)
        self.assertIn("application/json", resp.text)
        self.assertIn(json_payload, resp.text)

    def test_go_POST_without_body(self):
        resp = self.request_lua("""
            function main(splash)
              ok, reason = assert(splash:go{splash.args.url, http_method="POST",
                                     headers=headers,
                                     body=""})
              return splash:html()
            end
        """, {"url": self.mockurl('postrequest')})
        self.assertStatusCode(resp, 200)

    def test_splash_go_POST_baseurl(self):
        # if baseurl is passed request is processed differently
        # so this test can fail even if above test goes fine
        resp = self.request_lua("""
        function main(splash)
          formdata = {param1="foo", param2="bar"}
          ok, reason = splash:go{splash.args.url, http_method="post",
                                 body=form_body, baseurl="http://loc",
                                 formdata=formdata}
          return splash:html()
        end
        """, {"url": self.mockurl('postrequest')})
        self.assertStatusCode(resp, 200)
        self.assertTrue(
            "param2=bar&amp;param1=foo" in resp.text or
            "param1=foo&amp;param2=bar" in resp.text
            , resp.text)
        self.assertIn("application/x-www-form-urlencoded", resp.text)

    def test_splash_bad_http_method(self):
        # someone passes "BAD" as HTTP method
        resp = self.request_lua("""
        function main(splash)
          form_body = {param1="foo", param2="bar"}
          ok, reason = splash:go{splash.args.url, http_method="BAD",
                                 body=form_body, baseurl="http://loc"}
          return splash:html()
        end
        """, {"url": self.mockurl('postrequest')})
        self.assertStatusCode(resp, 400)
        self.assertIn('Unsupported HTTP method: BAD', resp.text)

    def test_formdata_and_body_error(self):
        resp = self.request_lua("""
        function main(splash)
          formdata = {param1="foo", param2="bar"}
          ok, reason = splash:go{splash.args.url, http_method="POST",
                                 body="some string", baseurl="http://loc",
                                 formdata=formdata}
          return splash:html()
        end
        """, {"url": self.mockurl('postrequest')})
        self.assertStatusCode(resp, 400)
        self.assertIn("formdata and body cannot be passed", resp.text)

    def test_formdata_in_bad_format(self):
        resp = self.request_lua("""
        function main(splash)
          formdata = "alfaomega"
          ok, reason = splash:go{splash.args.url, http_method="POST",
                                 baseurl="http://loc",
                                 formdata=formdata}
          return splash:html()
        end
        """, {"url": self.mockurl('postrequest')})
        self.assertStatusCode(resp, 400)
        self.assertIn("formdata argument for go() must be a Lua table", resp.text)

    def test_POST_body_not_string(self):
        resp = self.request_lua("""
        function main(splash)
          ok, reason = splash:go{splash.args.url, http_method="POST",
                                 baseurl="http://loc", body={a=1}}
          return splash:html()
        end
        """, {"url": self.mockurl('postrequest')})
        self.assertStatusCode(resp, 400)
        self.assertIn("request body must be a string", resp.text)


class ResourceTimeoutTest(BaseLuaRenderTest):
    if not qt_551_plus():
        pytestmark = pytest.mark.xfail(
            run=False,
            reason="resource_timeout doesn't work in Qt5 < 5.5.1. "
                   "See issue #269 for details."
        )

    def test_resource_timeout_aborts_first(self):
        resp = self.request_lua("""
        function main(splash)
            splash:on_request(function(req) req:set_timeout(0.1) end)
            local ok, err = splash:go{splash.args.url}
            return {err=err}
        end
        """, {"url": self.mockurl("slow.gif?n=4")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'err': 'render_error'})

    def test_resource_timeout_attribute(self):
        # request should be cancelled
        resp = self.request_lua("""
        function main(splash)
            splash.resource_timeout = 0.1
            assert(splash:go(splash.args.url))
        end
        """, {"url": self.mockurl("slow.gif?n=4")})
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message='render_error')

    def test_resource_timeout_attribute_priority(self):
        # set_timeout should take a priority
        resp = self.request_lua("""
        function main(splash)
            splash.resource_timeout = 0.1
            splash:on_request(function(req) req:set_timeout(10) end)
            assert(splash:go(splash.args.url))
        end
        """, {"url": self.mockurl("slow.gif?n=4")})
        self.assertStatusCode(resp, 200)

    def test_resource_timeout_read(self):
        resp = self.request_lua("""
        function main(splash)
            local default = splash.resource_timeout
            splash.resource_timeout = 0.1
            local updated = splash.resource_timeout
            return {default=default, updated=updated}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"default": 0, "updated": 0.1})

    def test_resource_timeout_zero(self):
        resp = self.request_lua("""
        function main(splash)
            splash.resource_timeout = 0
            assert(splash:go(splash.args.url))
        end
        """, {"url": self.mockurl("slow.gif?n=1")})
        self.assertStatusCode(resp, 200)

        resp = self.request_lua("""
        function main(splash)
            splash.resource_timeout = nil
            assert(splash:go(splash.args.url))
        end
        """, {"url": self.mockurl("slow.gif?n=1")})
        self.assertStatusCode(resp, 200)

    def test_resource_timeout_negative(self):
        resp = self.request_lua("""
        function main(splash)
            splash.resource_timeout = -1
            assert(splash:go(splash.args.url))
        end
        """, {"url": self.mockurl("slow.gif?n=1")})
        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='splash.resource_timeout')
        self.assertEqual(err['info']['line_number'], 3)


class ResultStatusCodeTest(BaseLuaRenderTest):
    def test_set_result_status_code(self):
        for code in [200, 404, 500, 999]:
            resp = self.request_lua("""
            function main(splash)
                splash:set_result_status_code(tonumber(splash.args.code))
                return "hello"
            end
            """, {'code': code})
            self.assertStatusCode(resp, code)
            self.assertEqual(resp.text, 'hello')

    def test_invalid_code(self):
        for code in ["foo", "", {'x': 3}, 0, -200, 195, 1000]:
            resp = self.request_lua("""
            function main(splash)
                splash:set_result_status_code(splash.args.code)
                return "hello"
            end
            """, {'code': code})
            err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)
            self.assertEqual(err['info']['splash_method'],
                             'set_result_status_code')


class SetUserAgentTest(BaseLuaRenderTest):
    def test_set_user_agent(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            local res1 = splash:html()

            splash:set_user_agent("Foozilla")
            splash:go(splash.args.url)
            local res2 = splash:html()

            splash:go(splash.args.url)
            local res3 = splash:html()

            return {res1=res1, res2=res2, res3=res3}
        end
        """, {"url": self.mockurl("getrequest")})

        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertIn("Mozilla", data["res1"])
        self.assertNotIn("Mozilla", data["res2"])
        self.assertNotIn("Mozilla", data["res3"])

        if six.PY3:
            self.assertNotIn("b'user-agent': b'Foozilla'", data["res1"])
            self.assertIn("b'user-agent': b'Foozilla'", data["res2"])
            self.assertIn("b'user-agent': b'Foozilla'", data["res3"])
        else:
            self.assertNotIn("'user-agent': 'Foozilla'", data["res1"])
            self.assertIn("'user-agent': 'Foozilla'", data["res2"])
            self.assertIn("'user-agent': 'Foozilla'", data["res3"])

    def test_set_user_agent_base_url(self):
        resp = self.request_lua("""
            function main(splash)
                splash:set_user_agent("Foozilla")
                splash:go{splash.args.url, baseurl="baseurl"}
                return splash:har()
            end
            """, {"url": self.mockurl("baseurl")})

        self.assertStatusCode(resp, 200)
        data = resp.json()
        headers = data["log"]["entries"][0]["request"]["headers"]
        self.assertEqual(len(headers), 1)
        self.assertEqual(headers[0]["value"], "Foozilla")

    def test_error(self):
        resp = self.request_lua("""
        function main(splash) splash:set_user_agent(123) end
        """)
        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)
        self.assertEqual(err['info']['splash_method'], 'set_user_agent')


class CookiesTest(BaseLuaRenderTest):
    def test_cookies(self, use_js=''):
        resp = self.request_lua("""
        function main(splash)
            local function cookies_after(url)
                splash:go(url)
                return splash:get_cookies()
            end

            local c0 = splash:get_cookies()
            local c1 = cookies_after(splash.args.url_1)
            local c2 = cookies_after(splash.args.url_2)

            splash:clear_cookies()
            local c3 = splash:get_cookies()

            local c4 = cookies_after(splash.args.url_2)
            local c5 = cookies_after(splash.args.url_1)

            splash:delete_cookies("foo")
            local c6 = splash:get_cookies()

            splash:delete_cookies{url="http://example.com"}
            local c7 = splash:get_cookies()

            splash:delete_cookies{url="http://localhost/"}
            local c8 = splash:get_cookies()

            splash:init_cookies(c2)
            local c9 = splash:get_cookies()

            return {c0=c0, c1=c1, c2=c2, c3=c3, c4=c4, c5=c5, c6=c6, c7=c7, c8=c8, c9=c9}
        end
        """, {
            "url_1": self.mockurl("set-cookie?key=foo&value=bar&use_js=%s" % use_js),
            "url_2": self.mockurl("set-cookie?key=egg&value=spam&use_js=%s" % use_js),
        })

        self.assertStatusCode(resp, 200)
        data = resp.json()

        cookie1 = {
            'name': 'foo',
            'value': 'bar',
            'domain': 'localhost',
            'path': '/',
            'httpOnly': False,
            'secure': False
        }
        cookie2 = {
            'name': 'egg',
            'value': 'spam',
            'domain': 'localhost',
            'path': '/',
            'httpOnly': False,
            'secure': False
        }
        self.assertEqual(data["c0"], [])
        self.assertEqual(data["c1"], [cookie1])
        self.assertEqual(data["c2"], [cookie1, cookie2])
        self.assertEqual(data["c3"], [])
        self.assertEqual(data["c4"], [cookie2])
        self.assertEqual(data["c5"], [cookie2, cookie1])
        self.assertEqual(data["c6"], [cookie2])
        self.assertEqual(data["c7"], [cookie2])
        self.assertEqual(data["c8"], [])
        self.assertEqual(data["c9"], data["c2"])

    def test_cookies_js(self):
        self.test_cookies('true')

    def test_add_cookie(self):
        resp = self.request_lua("""
        function main(splash)
            splash:add_cookie("baz", "egg")
            splash:add_cookie{"spam", "egg", domain="example.com"}
            splash:add_cookie{
                name="foo",
                value="bar",
                path="/",
                domain="localhost",
                expires="2016-07-24T19:20:30+02:00",
                secure=true,
                httpOnly=true,
            }
            return splash:get_cookies()
        end""")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), [
            {"name": "baz", "value": "egg", "path": "",
             "domain": "", "httpOnly": False, "secure": False},
            {"name": "spam", "value": "egg", "path": "",
             "domain": "example.com", "httpOnly": False, "secure": False},
            {"name": "foo", "value": "bar", "path": "/",
             "domain": "localhost", "httpOnly": True, "secure": True,
             "expires": "2016-07-24T19:20:30+02:00"},
        ])

    def test_init_cookies(self):
        resp = self.request_lua("""
        function main(splash)
            splash:init_cookies({
                {name="baz", value="egg"},
                {name="spam", value="egg", domain="example.com"},
                {
                    name="foo",
                    value="bar",
                    path="/",
                    domain="localhost",
                    expires="2016-07-24T19:20:30+02:00",
                    secure=true,
                    httpOnly=true,
                }
            })
            return splash:get_cookies()
        end""")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), [
            {"name": "baz", "value": "egg", "path": "",
             "domain": "", "httpOnly": False, "secure": False},
            {"name": "spam", "value": "egg", "path": "",
             "domain": "example.com", "httpOnly": False, "secure": False},
            {"name": "foo", "value": "bar", "path": "/",
             "domain": "localhost", "httpOnly": True, "secure": True,
             "expires": "2016-07-24T19:20:30+02:00"},
        ])


class CurrentUrlTest(BaseLuaRenderTest):
    def request_url(self, url, wait=0.0):
        return self.request_lua("""
        function main(splash)
            local ok, res = splash:go(splash.args.url)
            splash:wait(splash.args.wait)
            return {ok=ok, res=res, url=splash:url()}
        end
        """, {"url": url, "wait": wait})

    def assertCurrentUrl(self, go_url, url=None, wait=0.0):
        if url is None:
            url = go_url
        resp = self.request_url(go_url, wait)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json()["url"], url)

    def test_start(self):
        resp = self.request_lua("function main(splash) return splash:url() end")
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "")

    def test_blank(self):
        self.assertCurrentUrl("about:blank")

    def test_not_redirect(self):
        self.assertCurrentUrl(self.mockurl("getrequest"))

    def test_jsredirect(self):
        self.assertCurrentUrl(self.mockurl("jsredirect"))
        self.assertCurrentUrl(
            self.mockurl("jsredirect"),
            self.mockurl("jsredirect-target"),
            wait=0.5,
        )


class DisableScriptsTest(BaseLuaRenderTest):
    def test_nolua(self):
        with SplashServer(extra_args=['--disable-lua']) as splash:
            # Check that Lua is disabled in UI
            resp = requests.get(splash.url("/"))
            self.assertStatusCode(resp, 200)
            self.assertIn('"lua_enabled": false', resp.text)

            script = "function main(splash) return 'foo' end"

            # Check that /execute doesn't work
            resp = requests.get(
                url=splash.url("execute"),
                params={'lua_source': script},
            )
            self.assertStatusCode(resp, 404)


class SandboxTest(BaseLuaRenderTest):
    def assertTooMuchCPU(self, resp, subtype=ScriptError.LUA_ERROR):
        return self.assertScriptError(resp, subtype,
                                      message="script uses too much CPU")

    def assertTooMuchMemory(self, resp, subtype=ScriptError.LUA_ERROR):
        return self.assertScriptError(resp, subtype,
                                      message="script uses too much memory")

    def test_sandbox_string_function(self):
        resp = self.request_lua("""
        function main(splash)
            return string.rep("x", 10000)
        end
        """)
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message="nil value")
        self.assertErrorLineNumber(resp, 3)

    def test_sandbox_string_method(self):
        resp = self.request_lua("""
        function main(splash)
            return ("x"):rep(10000)
        end
        """)
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message="nil value")
        self.assertErrorLineNumber(resp, 3)

    def test_non_sandboxed_string_method(self):
        resp = self.request_lua("""
        function main(splash)
            return ("X"):lower()
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "x")

    def test_infinite_loop(self):
        resp = self.request_lua("""
        function main(splash)
            local x = 0
            while true do
                x = x + 1
            end
            return x
        end
        """)
        self.assertTooMuchCPU(resp)

    def test_infinite_loop_toplevel(self):
        resp = self.request_lua("""
        x = 0
        while true do
            x = x + 1
        end
        function main(splash)
            return 5
        end
        """)
        self.assertTooMuchCPU(resp, ScriptError.LUA_INIT_ERROR)

    def test_infinite_loop_memory(self):
        resp = self.request_lua("""
        function main(splash)
            t = {}
            while true do
                t = { t }
            end
            return t
        end
        """)
        # it can be either memory or CPU
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message="too much")

    def test_memory_attack(self):
        resp = self.request_lua("""
        function main(splash)
            local s = "aaaaaaaaaaaaaaaaaaaa"
            while true do
                s = s..s
            end
            return s
        end
        """)
        self.assertTooMuchMemory(resp)

    def test_memory_attack_in_callback(self):
        resp = self.request_lua("""
        function main(splash)
            local s = "aaaaaaaaaaaaaaaaaaaa"
            splash:call_later(function()
                while true do
                    s = s..s
                end
            end)
            splash:wait(0.5)
            return s
        end
        """)
        self.assertTooMuchMemory(resp)

    def test_memory_attack_toplevel(self):
        resp = self.request_lua("""
        s = "aaaaaaaaaaaaaaaaaaaa"
        while true do
            s = s..s
        end
        function main(splash)
            return s
        end
        """)
        self.assertTooMuchMemory(resp, ScriptError.LUA_INIT_ERROR)

    def test_billion_laughs(self):
        resp = self.request_lua("""
        s = "s"
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s s = s .. s
        function main() end
        """)
        self.assertTooMuchMemory(resp, ScriptError.LUA_INIT_ERROR)

    def test_disable_sandbox(self):
        # dofile function should be always sandboxed
        is_sandbox = "function main(splash) return {s=(dofile==nil)} end"

        resp = self.request_lua(is_sandbox)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"s": True})

        with SplashServer(extra_args=['--disable-lua-sandbox']) as splash:
            resp = requests.get(
                url=splash.url("execute"),
                params={'lua_source': is_sandbox},
            )
            self.assertStatusCode(resp, 200)
            self.assertEqual(resp.json(), {"s": False})


class RequireTest(BaseLuaRenderTest):
    def _set_title(self, title):
        return """
        splash:set_content([[
        <html>
          <head>
            <title>%s</title>
          </head>
        </html>
        ]])
        """ % title

    def assertNoRequirePathsLeaked(self, resp):
        self.assertNotIn("/lua", resp.text)
        self.assertNotIn("init.lua", resp.text)

    def test_splash_patching(self):
        title = "TEST"
        resp = self.request_lua("""
        require "utils_patch"
        function main(splash)
            %(set_title)s
            return splash:get_document_title()
        end
        """ % dict(set_title=self._set_title(title)))
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, title)

    def test_splash_patching_no_require(self):
        resp = self.request_lua("""
        function main(splash)
            %(set_title)s
            return splash:get_document_title()
        end
        """ % dict(set_title=self._set_title("TEST")))
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message="get_document_title")
        self.assertNoRequirePathsLeaked(resp)

    def test_require_unsafe(self):
        for module in ['splash', 'wraputils', 'completer', 'sandbox', 'extras']:
            resp = self.request_lua("""
            require('%s')
            function main(splash) return "hello" end
            """ % module)
            self.assertScriptError(resp, ScriptError.LUA_INIT_ERROR)
            self.assertErrorLineNumber(resp, 2)
            self.assertNoRequirePathsLeaked(resp)

    def test_require_not_whitelisted(self):
        resp = self.request_lua("""
        local utils = require("utils")
        local secret = require("secret")
        function main(splash) return "hello" end
        """)
        self.assertScriptError(resp, ScriptError.LUA_INIT_ERROR)
        self.assertErrorLineNumber(resp, 3)
        self.assertNoRequirePathsLeaked(resp)

    def test_require_non_existing(self):
        resp = self.request_lua("""
        local foobar = require("foobar")
        function main(splash) return "hello" end
        """)
        self.assertScriptError(resp, ScriptError.LUA_INIT_ERROR)
        self.assertNoRequirePathsLeaked(resp)
        self.assertErrorLineNumber(resp, 2)

    def test_require_non_existing_whitelisted(self):
        resp = self.request_lua("""
        local non_existing = require("non_existing")
        function main(splash) return "hello" end
        """)
        self.assertScriptError(resp, ScriptError.LUA_INIT_ERROR)
        self.assertNoRequirePathsLeaked(resp)
        self.assertErrorLineNumber(resp, 2)

    def test_module(self):
        title = "TEST"
        resp = self.request_lua("""
        local utils = require "utils"
        function main(splash)
            %(set_title)s
            return utils.get_document_title(splash)
        end
        """ % dict(set_title=self._set_title(title)))
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, title)

    def test_module_require_unsafe_from_safe(self):
        resp = self.request_lua("""
        function main(splash)
            return require("utils").hello
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "world")


class HarTest(BaseLuaRenderTest):
    def test_har_empty(self):
        resp = self.request_lua("""
        function main(splash)
            return splash:har()
        end
        """)
        self.assertStatusCode(resp, 200)
        har = resp.json()["log"]
        self.assertEqual(har["entries"], [])

    def test_har_about_blank(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go("about:blank")
            return splash:har()
        end
        """)
        self.assertStatusCode(resp, 200)
        har = resp.json()["log"]
        self.assertEqual(har["entries"], [])

    def test_har_reset(self):
        resp = self.request_lua("""
        treat = require("treat")
        function main(splash)
            splash:go(splash.args.url)
            splash:go(splash.args.url)
            local har1 = splash:har()
            splash:har_reset()
            local har2 = splash:har()
            splash:go(splash.args.url)
            local har3 = splash:har()
            return treat.as_array({har1, har2, har3})
        end
        """, {'url': self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        har1, har2, har3 = resp.json()

        self.assertEqual(len(har1['log']['entries']), 2)
        self.assertEqual(har2['log']['entries'], [])
        self.assertEqual(len(har3['log']['entries']), 1)

    def test_har_reset_argument(self):
        resp = self.request_lua("""
        treat = require("treat")
        function main(splash)
            splash:go(splash.args.url)
            local har1 = splash:har()
            splash:go(splash.args.url)
            local har2 = splash:har{reset=true}
            local har3 = splash:har()
            splash:go(splash.args.url)
            local har4 = splash:har()
            return treat.as_array({har1, har2, har3, har4})
        end
        """, {'url': self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        har1, har2, har3, har4 = resp.json()

        self.assertEqual(len(har1['log']['entries']), 1)
        self.assertEqual(len(har2['log']['entries']), 2)
        self.assertEqual(har3['log']['entries'], [])
        self.assertEqual(len(har4['log']['entries']), 1)

    def test_har_reset_inprogress(self):
        resp = self.request_lua("""
        treat = require("treat")
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.5)
            local har1 = splash:har{reset=true}
            splash:wait(2.5)
            local har2 = splash:har()
            return treat.as_array({har1, har2})
        end
        """, {'url': self.mockurl("show-image?n=2.0&js=0.1")})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        har1, har2 = data[0]["log"], data[1]["log"]

        self.assertEqual(len(har1['entries']), 2)
        self.assertEqual(har1['entries'][0]['_splash_processing_state'],
                         HarBuilder.REQUEST_FINISHED)
        self.assertEqual(har1['entries'][1]['_splash_processing_state'],
                         HarBuilder.REQUEST_HEADERS_RECEIVED)


class AutoloadTest(BaseLuaRenderTest):
    def test_autoload(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:autoload("window.FOO = 'bar'"))

            splash:go(splash.args.url)
            local foo1 = splash:evaljs("FOO")

            splash:evaljs("window.FOO = 'spam'")
            local foo2 = splash:evaljs("FOO")

            splash:go(splash.args.url)
            local foo3 = splash:evaljs("FOO")
            return {foo1=foo1, foo2=foo2, foo3=foo3}
        end
        """, {"url": self.mockurl("getrequest")})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data, {"foo1": "bar", "foo2": "spam", "foo3": "bar"})

    def test_autoload_remote(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:autoload(splash.args.eggspam_url))
            assert(splash:go(splash.args.url))
            local egg = splash:jsfunc("egg")
            return egg()
        end
        """, {
            "url": self.mockurl("getrequest"),
            "eggspam_url": self.mockurl("eggspam.js"),
        })
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "spam")

    def test_autoload_bad(self):
        resp = self.request_lua("""
        function main(splash)
            local ok, reason = splash:autoload(splash.args.bad_url)
            return {ok=ok, reason=reason}
        end
        """, {"bad_url": self.mockurl("--non-existing--")})
        self.assertStatusCode(resp, 200)
        self.assertNotIn("ok", resp.json())
        self.assertIn("404", resp.json()["reason"])

    def test_noargs(self):
        resp = self.request_lua("""
        function main(splash)
            splash:autoload()
        end
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)
        self.assertErrorLineNumber(resp, 3)

    def test_autoload_reset(self):
        resp = self.request_lua("""
        function main(splash)
            splash:autoload([[window.FOO = 'foo']])
            splash:autoload([[window.BAR = 'bar']])

            splash:go(splash.args.url)
            local foo1 = splash:evaljs("window.FOO")
            local bar1 = splash:evaljs("window.BAR")

            splash:autoload_reset()
            splash:go(splash.args.url)
            local foo2 = splash:evaljs("window.FOO")
            local bar2 = splash:evaljs("window.BAR")

            return {foo1=foo1, bar1=bar1, foo2=foo2, bar2=bar2}
        end
        """, {"url": self.mockurl("getrequest")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"foo1": "foo", "bar1": "bar"})


class HttpGetTest(BaseLuaRenderTest):
    def test_get(self):
        resp = self.request_lua("""
        function main(splash)
            local reply = splash:http_get(splash.args.url)
            splash:wait(0.1)
            return reply.body
        end
        """, {"url": self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(JsRender.template, resp.text)

    def test_get_with_default_headers(self):
        resp = self.request_lua("""
        function main(splash)
            response = nil
            splash:on_response(function (res)
                response = res
            end)
            assert(splash:http_get(splash.args.url))
            return response.request.headers
        end
        """, {"url": self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        headers = resp.json()
        self.assertNotEqual(len(headers), 0)
        self.assertEqual(len(headers), 1)
        self.assertIn("Mozilla/5.0", headers["user-agent"])

    def test_get_with_custom_headers(self):
        resp = self.request_lua("""
        function main(splash)
            splash:set_custom_headers({
                ["Header-1"] = "Value 1",
                ["Header-2"] = "Value 2",
                })
            response = assert(splash:http_get(splash.args.url))
            return response.request.headers
        end
        """, {"url": self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        headers = resp.json()
        self.assertNotEqual(len(headers), 0)
        self.assertEqual(headers["Header-1"], "Value 1")
        self.assertEqual(headers["Header-2"], "Value 2")
        self.assertIn("user-agent", headers)

    def test_get_with_custom_ua(self):
        resp = self.request_lua("""
        function main(splash)
            splash:set_user_agent("CUSTOM UA")
            response = assert(splash:http_get(splash.args.url))
            return response.request.headers
        end
        """, {"url": self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        headers = resp.json()
        self.assertNotEqual(len(headers), 0)
        self.assertEqual(headers["user-agent"], "CUSTOM UA")

    def test_get_with_custom_ua_in_headers(self):
        resp = self.request_lua("""
        function main(splash)
            response = assert(splash:http_get{splash.args.url, headers={["user-agent"]="Value 1"}})
            return response.request.headers
        end
        """, {"url": self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        headers = resp.json()
        self.assertNotEqual(len(headers), 0)
        self.assertEqual(headers["user-agent"], "Value 1")

    def test_get_with_custom_ua_in_headers_and_set_with_splash(self):
        resp = self.request_lua("""
            function main(splash)
                splash:set_user_agent("CUSTOM UA")
                response1 = assert(splash:http_get(splash.args.url))
                response2 = assert(splash:http_get{splash.args.url, headers={["user-agent"]="Value 1"}})
                response3 = assert(splash:http_get(splash.args.url))

                return {
                    result1=response1.request.headers,
                    result2=response2.request.headers,
                    result3=response3.request.headers
                }
            end
            """, {"url": self.mockurl("jsrender")})
        self.assertStatusCode(resp, 200)
        resp = resp.json()
        headers1, headers2, headers3 = resp["result1"], resp["result2"], resp["result3"]
        self.assertTrue(all("user-agent" in h for h in (headers1, headers2, headers3)))
        self.assertEqual(headers1["user-agent"], "CUSTOM UA")
        self.assertEqual(headers2["user-agent"], "Value 1")
        self.assertEqual(headers3["user-agent"], "CUSTOM UA")

    def test_ua_on_rendering(self):
        resp = self.request_lua("""
            function main(splash)
                treat = require("treat")
                local result = treat.as_array({})
                splash:on_response_headers(function (response)
                    result[#result+1] = response.request.headers
                end)

                response = assert(splash:go{splash.args.url, headers={["user-agent"]="Value 1"}})
                return result
            end
            """, {"url": self.mockurl("subresources")})
        self.assertStatusCode(resp, 200)
        resp = resp.json()
        uas = [r.get("User-Agent", r.get("user-agent")) for r in resp]
        self.assertTrue(all(h == "Value 1" for h in uas))

    def test_bad_url(self):
        resp = self.request_lua("""
        function main(splash)
            return splash:http_get(splash.args.url).info
        end
        """, {"url": self.mockurl("--bad-url--")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json()["status"], 404)

    def test_headers(self):
        resp = self.request_lua("""
        function main(splash)
            local resp = splash:http_get{
                splash.args.url,
                headers={
                    ["Custom-Header"] = "Header Value",
                }
            }
            return resp.info
        end
        """, {"url": self.mockurl("getrequest")})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data["status"], 200)
        self.assertIn(b"Header Value", get_response_body_bytes(data))

    def test_redirects_follow(self):
        resp = self.request_lua("""
        function main(splash)
            return splash:http_get(splash.args.url).info
        end
        """, {"url": self.mockurl("http-redirect?code=302")})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data["status"], 200)
        self.assertNotIn(b"redirect to", get_response_body_bytes(data))
        self.assertIn(b"GET request", get_response_body_bytes(data))

    def test_redirects_nofollow(self):
        resp = self.request_lua("""
        function main(splash)
            local resp = splash:http_get{url=splash.args.url, follow_redirects=false}
            return resp.info
        end
        """, {"url": self.mockurl("http-redirect?code=302")})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data["status"], 302)
        self.assertEqual(data["redirectURL"], "/getrequest?http_code=302")
        self.assertIn(b"302 redirect to", get_response_body_bytes(data))

    def test_noargs(self):
        resp = self.request_lua("""
        function main(splash)
            splash:http_get()
        end
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_httpget_nonascii_nonutf8(self):
        resp = self.request_lua("""
        function main(splash)
            local resp = splash:http_get{splash.args.url}
            return resp.body
        end
        """, {"url": self.mockurl("cp1251")})
        self.assertStatusCode(resp, 200)
        self.assertIn(u'проверка', resp.content.decode('cp1251'))
        self.assertEqual(resp.headers['Content-Type'], "text/html; charset=windows-1251")

    def test_response_attributes_readonly(self):
        for attr in ["url", "status", "ok"]:
            resp = self.request_lua("""
            function main(splash)
                local resp = splash:http_get{splash.args.url}
                resp[splash.args.attr] = "foo"
                return "ok"
            end
            """, {"url": self.mockurl("getrequest"), "attr": attr})
            self.assertScriptError(resp, ScriptError.LUA_ERROR,
                                   message="read-only")

    def test_response_attributes_redirected(self):
        request_url = self.mockurl("http-redirect?code=302")
        response_url = self.mockurl("getrequest?http_code=302")
        resp = self.request_lua("""
        function main(splash)
            local headers={["X-My-HeaDer"]="123"}
            local resp = splash:http_get{
                url=splash.args.url,
                follow_redirects=true,
                headers=headers
            }
            return {
                url=resp.url,
                status=resp.status,
                headers=resp.headers,
                ok=resp.ok,
                request={
                    info=resp.request.info,
                    method=resp.request.method,
                    url=resp.request.url,
                    headers=resp.request.headers,
                },
            }
        end
        """, {"url": request_url})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data['url'], response_url)
        self.assertEqual(data['status'], 200)
        self.assertEqual(data['ok'], True)
        self.assertEqual(data['headers']['Content-Type'], 'text/html')

        req = data['request']
        self.assertEqual(req['method'], 'GET')
        self.assertEqual(req['headers'].get('X-My-HeaDer'), '123')
        self.assertEqual(req['info']['httpVersion'], 'HTTP/1.1')  # har record
        # self.assertEqual(req['url'], response_url)  # XXX: is it correct?

    def test_response_attributes_redirect(self):
        request_url = self.mockurl("http-redirect?code=302")
        resp = self.request_lua("""
        function main(splash)
            local headers={["X-My-HeaDer"]="123"}
            local resp = splash:http_get{
                url=splash.args.url,
                follow_redirects=false,
                headers=headers
            }
            return {
                url=resp.url,
                status=resp.status,
                headers=resp.headers,
                ok=resp.ok,
                request={
                    info=resp.request.info,
                    method=resp.request.method,
                    url=resp.request.url,
                    headers=resp.request.headers,
                },
            }
        end
        """, {"url": request_url})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data['url'], request_url)
        self.assertEqual(data['status'], 302)
        self.assertEqual(data['ok'], True)
        self.assertEqual(data['headers']['Location'], "/getrequest?http_code=302")

        req = data['request']
        self.assertEqual(req['method'], 'GET')
        self.assertEqual(req['headers'].get("X-My-HeaDer"), '123')
        self.assertEqual(req['info']['httpVersion'], 'HTTP/1.1')  # har record
        self.assertEqual(req['url'], request_url)

    def test_access_attributes_twice(self):
        url = self.mockurl("jsrender")
        resp = self.request_lua("""
        function main(splash)
            local resp = splash:http_get{splash.args.url}
            return {
                info1=resp.info,
                info2=resp.info,
                body1=resp.body,
                body2=resp.body,
            }
        end
        """, {"url": url})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data['info1'], data['info2'])
        self.assertEqual(data['body1'], data['body2'])


class HttpPostTest(BaseLuaRenderTest):
    def test_post(self):
        resp = self.request_lua("""
        function main(splash)
            body = "foo=one&bar=two"
            return splash:http_post{url=splash.args.url, body=body}.info
        end
        """, {"url": self.mockurl("postrequest")})
        self.assertStatusCode(resp, 200)
        info = resp.json()
        self.assertTrue(info["ok"])
        self.assertIn(b"foo=one&bar=two", get_response_body_bytes(info))

    def test_post_body_not_string(self):
        resp = self.request_lua("""
        function main(splash)
            body = {alfa=12}
            return splash:http_post{url=splash.args.url, body=body}
        end
        """, {"url": self.mockurl("postrequest")})
        self.assertStatusCode(resp, 400)
        self.assertIn("body argument for splash:http_post() must be string", resp.text)

    def test_post_without_body(self):
        resp = self.request_lua("""
        function main(splash)
            body = ""
            return splash:http_post{url=splash.args.url, body=body}.body
        end
        """, {"url": self.mockurl("postrequest")})
        self.assertStatusCode(resp, 200)
        self.assertIn("POST", resp.text)

    def test_redirect_after_post_in_go(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go{url=splash.args.url, body=body, http_method="POST"})
            return splash:html()
        end
        """, {"url": self.mockurl("http-redirect")})
        self.assertStatusCode(resp, 200)
        self.assertIn("GET request", resp.text)

    def test_redirect_after_post_in_http_post(self):
        post_body = "foo=bar&alfa=beta"
        resp = self.request_lua("""
            function main(splash)
                return splash:http_post{url=splash.args.url, body='%s'}.info
            end
            """ % post_body, {"url": self.mockurl("http-redirect")})
        self.assertStatusCode(resp, 200)
        info = resp.json()
        self.assertIn(b"GET request", get_response_body_bytes(info))
        self.assertIn(post_body, info["url"])
        self.assertEqual(info["status"], 200)

    def test_response_attributes(self):
        resp = self.request_lua("""
        function main(splash)
            local resp = splash:http_post{splash.args.url}
            return {
                url=resp.url,
                status=resp.status,
                headers=resp.headers,
                ok=resp.ok,
            }
        end
        """, {"url": self.mockurl("postrequest")})
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertEqual(data['url'], self.mockurl("postrequest"))
        self.assertEqual(data['status'], 200)
        self.assertEqual(data['ok'], True)
        self.assertEqual(data['headers']['Content-Type'], 'text/plain; charset=utf-8')

    def test_binary_post_body(self):
        postbody = u'привет'.encode('cp1251')
        resp = self.request_lua("""
            base64 = require("base64")
            treat = require("treat")
            function main(splash)
                local body = base64.decode(splash.args.postbody)
                local resp = splash:http_post{
                    url=splash.args.url,
                    body=treat.as_binary(body)
                }
                return resp.body
            end
            """, {
            "url": self.mockurl("postrequest"),
            "postbody": base64.b64encode(postbody)
        })
        self.assertStatusCode(resp, 200)
        self.assertIn(repr(postbody), resp.text)


class NavigationLockingTest(BaseLuaRenderTest):
    def test_lock_navigation(self):
        url = self.mockurl("jsredirect")
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash:lock_navigation()
            splash:wait(0.3)
            return splash:url()
        end
        """, {"url": url})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, url)

    def test_unlock_navigation(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash:lock_navigation()
            splash:unlock_navigation()
            splash:wait(0.3)
            return splash:url()
        end
        """, {"url": self.mockurl("jsredirect")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, self.mockurl("jsredirect-target"))

    def test_go_navigation_locked(self):
        resp = self.request_lua("""
        function main(splash)
            splash:lock_navigation()
            local ok, reason = splash:go(splash.args.url)
            return {ok=ok, reason=reason}
        end
        """, {"url": self.mockurl("jsredirect"), "timeout": 1.0})
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"reason": "navigation_locked"})


class SetContentTest(BaseLuaRenderTest):
    def test_set_content(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:set_content("<html><head></head><body><h1>Hello</h1></body></html>"))
            return {
                html = splash:html(),
                url = splash:url(),
            }
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            "html": "<html><head></head><body><h1>Hello</h1></body></html>",
            "url": "",
        })

    def test_unicode(self):
        resp = self.request_lua(u"""
        function main(splash)
            assert(splash:set_content("проверка"))
            return splash:html()
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertIn(u'проверка', resp.text)

    def test_related_resources(self):
        script = """
        function main(splash)
            splash:set_content{
                data = [[
                    <html><body>
                        <img width=50 heigth=50 src="/slow.gif?n=0.2">
                    </body></html>
                ]],
                baseurl = splash.args.base,
            }
            return splash:png()
        end
        """
        resp = self.request_lua(script, {"base": self.mockurl("")})
        self.assertStatusCode(resp, 200)
        img = Image.open(BytesIO(resp.content))
        self.assertEqual((0, 0, 0, 255), img.getpixel((10, 10)))

        # the same, but with a bad base URL
        resp = self.request_lua(script, {"base": ""})
        self.assertStatusCode(resp, 200)
        img = Image.open(BytesIO(resp.content))
        self.assertNotEqual((0, 0, 0, 255), img.getpixel((10, 10)))

    def test_url(self):
        resp = self.request_lua("""
        function main(splash)
            splash:set_content{"hey", baseurl="http://example.com/foo"}
            return splash:url()
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "http://example.com/foo")


class GetPerfStatsTest(BaseLuaRenderTest):
    def test_get_perf_stats(self):
        func = """
        function main(splash)
            return splash:get_perf_stats()
        end
        """
        out = self.request_lua(func).json()
        self.assertEqual(sorted(list(out.keys())),
                         sorted(['walltime', 'cputime', 'maxrss']))
        self.assertIsInstance(out['cputime'], numbers.Real)
        self.assertIsInstance(out['walltime'], numbers.Real)
        self.assertIsInstance(out['maxrss'], numbers.Integral)
        self.assertLess(out['cputime'], 1000.)
        self.assertLess(0., out['cputime'])
        # Should be safe to assume that splash process consumes between 1Mb
        # and 1Gb of RAM, right?
        self.assertLess(1E6, out['maxrss'])
        self.assertLess(out['maxrss'], 1E9)
        # I wonder if we could break this test...
        now = time.time()
        self.assertLess(now - 120, out['walltime'])
        self.assertLess(out['walltime'], now)


class WindowSizeTest(BaseLuaRenderTest):
    """This is a test for window & viewport size interaction in Lua scripts."""

    GET_DIMS_AFTER_SCRIPT = """
function get_dims(splash)
    return {
        inner = splash:evaljs("window.innerWidth") .. "x" .. splash:evaljs("window.innerHeight"),
        outer = splash:evaljs("window.outerWidth") .. "x" .. splash:evaljs("window.outerHeight"),
        client = (splash:evaljs("document.documentElement.clientWidth") .. "x"
                  .. splash:evaljs("document.documentElement.clientHeight"))
    }
end

function main(splash)
    alter_state(splash)
    return get_dims(splash)
end

function alter_state(splash)
%s
end
"""

    def return_json_from_lua(self, script, **kwargs):
        resp = self.request_lua(script, kwargs)
        if resp.ok:
            return resp.json()
        else:
            raise RuntimeError(resp.content)

    def get_dims_after(self, lua_script, **kwargs):
        return self.return_json_from_lua(
            self.GET_DIMS_AFTER_SCRIPT % lua_script, **kwargs)

    def assertSizeAfter(self, lua_script, etalon, **kwargs):
        out = self.get_dims_after(lua_script, **kwargs)
        self.assertEqual(out, etalon)

    def test_get_viewport_size(self):
        script = """
        function main(splash)
        local w, h = splash:get_viewport_size()
        return {width=w, height=h}
        end
        """
        out = self.return_json_from_lua(script)
        w, h = map(int, defaults.VIEWPORT_SIZE.split('x'))
        self.assertEqual(out, {'width': w, 'height': h})

    def test_default_dimensions(self):
        self.assertSizeAfter("",
                             {'inner': defaults.VIEWPORT_SIZE,
                              'outer': defaults.VIEWPORT_SIZE,
                              'client': defaults.VIEWPORT_SIZE})

    def test_set_sizes_as_table(self):
        self.assertSizeAfter('splash:set_viewport_size{width=111, height=222}',
                             {'inner': '111x222',
                              'outer': defaults.VIEWPORT_SIZE,
                              'client': '111x222'})
        self.assertSizeAfter('splash:set_viewport_size{height=333, width=444}',
                             {'inner': '444x333',
                              'outer': defaults.VIEWPORT_SIZE,
                              'client': '444x333'})

    def test_viewport_size_roundtrips(self):
        self.assertSizeAfter(
            'splash:set_viewport_size(splash:get_viewport_size())',
            {'inner': defaults.VIEWPORT_SIZE,
             'outer': defaults.VIEWPORT_SIZE,
             'client': defaults.VIEWPORT_SIZE})

    def test_viewport_size(self):
        self.assertSizeAfter('splash:set_viewport_size(2000, 2000)',
                             {'inner': '2000x2000',
                              'outer': defaults.VIEWPORT_SIZE,
                              'client': '2000x2000'})

    def test_viewport_size_validation(self):
        cases = [
            ('()', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 2 required positional arguments:*'),
            ('{}', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 2 required positional arguments:*'),
            ('(1)', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 1 required positional argument:*'),
            ('{1}', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 1 required positional argument:*'),
            ('(1, nil)', 'a number is required', None),
            ('{1, nil}', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 1 required positional argument:*'),
            ('(nil, 1)', 'a number is required', None),
            ('{nil, 1}', 'a number is required', None),
            ('{width=1}', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 1 required positional argument:*'),
            ('{width=1, nil}', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 1 required positional argument:*'),
            ('{nil, width=1}', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 1 required positional argument:*'),
            ('{height=1}', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 1 required positional argument:*'),
            ('{height=1, nil}', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 1 required positional argument:*'),
            ('{nil, height=1}', 'set_viewport_size.* takes exactly 3 arguments',
             'set_viewport_size.* missing 1 required positional argument:*'),

            ('{100, width=200}', 'set_viewport_size.* got multiple values.*width', None),
            # This thing works.
            # ('{height=200, 100}', 'set_viewport_size.* got multiple values.*width'),

            ('{100, "a"}', 'a number is required', None),
            ('{100, {}}', 'a number is required', None),

            ('{100, -1}', 'Viewport is out of range', None),
            ('{100, 0}', 'Viewport is out of range', None),
            ('{100, 99999}', 'Viewport is out of range', None),
            ('{1, -100}', 'Viewport is out of range', None),
            ('{0, 100}', 'Viewport is out of range', None),
            ('{99999, 100}', 'Viewport is out of range', None),
        ]

        def run_test(size_str):
            self.get_dims_after('splash:set_viewport_size%s' % size_str)

        for size_str, errmsg_py2, errmsg_py3 in cases:
            if not errmsg_py3:
                errmsg_py3 = errmsg_py2
            if six.PY3:
                self.assertRaisesRegexp(RuntimeError, errmsg_py3, run_test, size_str)
            else:
                self.assertRaisesRegexp(RuntimeError, errmsg_py2, run_test, size_str)

    def test_viewport_full(self):
        w = int(defaults.VIEWPORT_SIZE.split('x')[0])
        self.assertSizeAfter('splash:go(splash.args.url);'
                             'splash:wait(0.1);'
                             'splash:set_viewport_full();',
                             {'inner': '%dx2000' % w,
                              'outer': defaults.VIEWPORT_SIZE,
                              'client': '%dx2000' % w},
                             url=self.mockurl('tall'))

    def test_set_viewport_full_returns_dimensions(self):
        script = """
        function main(splash)
        assert(splash:go(splash.args.url))
        assert(splash:wait(0.1))
        local w, h = splash:set_viewport_full()
        return {width=w, height=h}
        end
        """
        out = self.return_json_from_lua(script, url=self.mockurl('tall'))
        w, h = map(int, defaults.VIEWPORT_SIZE.split('x'))
        self.assertEqual(out, {'width': w, 'height': 2000})

    def test_render_all_restores_viewport_size(self):
        script = """
        treat = require("treat")
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))
            local before = treat.as_array({splash:get_viewport_size()})
            png = splash:png{render_all=true}
            local after = treat.as_array({splash:get_viewport_size()})
            return {before=before, after=after, png=png}
        end
        """
        out = self.return_json_from_lua(script, url=self.mockurl('tall'))
        w, h = map(int, defaults.VIEWPORT_SIZE.split('x'))
        self.assertEqual(out['before'], [w, h])
        self.assertEqual(out['after'], [w, h])
        # 2000px is hardcoded in that html
        img = Image.open(BytesIO(base64.b64decode(out['png'])))
        self.assertEqual(img.size, (w, 2000))

    def test_set_viewport_size_changes_contents_size_immediately(self):
        # GH167
        script = """
treat = require("treat")
function main(splash)
splash:set_viewport_size(1024, 768)
assert(splash:set_content([[
<html>
<body style="min-width: 800px; margin: 0px">&nbsp;</body>
</html>
]]))
result = {}
result.before = treat.as_array({splash:set_viewport_full()})
splash:set_viewport_size(640, 480)
result.after = treat.as_array({splash:set_viewport_full()})
return result
end
        """
        out = self.return_json_from_lua(script)
        self.assertEqual(out,
                         {'before': [1024, 768],
                          'after': [800, 480]})

    @pytest.mark.xfail
    def test_viewport_full_raises_error_if_fails_in_script(self):
        # XXX: for local resources loadFinished event generally arrives after
        # initialLayoutCompleted, so the error doesn't manifest itself.
        self.assertRaisesRegexp(RuntimeError, "zyzzy",
                                self.get_dims_after,
                                """
                                splash:go(splash.args.url)
                                splash:set_viewport_full()
                                """, url=self.mockurl('delay'))


class RenderRegionTest(BaseLuaRenderTest):
    def _test_render_region_impl(self, **kwargs):
        script = """
        treat = require('treat')
        function main(splash)
            local args = splash.args
            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)
            local full = splash:png()
            local coords = {args.left, args.top, args.right, args.bottom}
            local shot1 = splash:png{region=coords, scale_method=args.scale_method}
            treat.as_array(coords)
            local shot2 = splash:png{region=coords, scale_method=args.scale_method}
            return {shots=treat.as_array({shot1, shot2}), full=full}
        end
        """
        region = 300, 50, 700, 110
        region_size = 400, 60
        resp = self.request_lua(script, dict(
            url=self.mockurl('red-green'),
            left=region[0], top=region[1], right=region[2], bottom=region[3],
            scale_method=kwargs.get('scale_method', 'raster'),
        ))
        self.assertStatusCode(resp, 200)
        out = resp.json()
        full_img = Image.open(BytesIO(base64.b64decode(out['full'])))
        for shot in out['shots']:
            region_img = Image.open(BytesIO(base64.b64decode(shot)))
            self.assertEqual(region_img.size, region_size)
            self.assertImagesEqual(full_img.crop(region), region_img)

    def test_render_region_raster(self):
        self._test_render_region_impl(scale_method='raster')

    def test_render_region_vector(self):
        self._test_render_region_impl(scale_method='vector')

    def test_empty_rect(self):
        script = """
        function main(splash)
            splash:set_viewport_size(1024, 768)
            splash:go(splash.args.url)
            splash:wait(0.1)
            local img = assert(splash:png{region={10, 10, 10, 10}})
            return {img=img}
        end
        """
        resp = self.request_lua(script, {'url': self.mockurl('red-green')})
        self.assertScriptError(resp, ScriptError.LUA_ERROR, 'assertion')

    def _test_render_region_with_resizing_impl(self, scale_method):
        script = """
        function main(splash)
            local args = splash.args
            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)
            local region = {args.left, args.top, args.right, args.bottom}
            local full = splash:png()
            local shot = splash:png{
                region=region,
                scale_method=args.scale_method,
                width=args.width,
            }
            return {shot=shot, full=full}
        end
        """
        region = (300, 50, 700, 110)
        resp = self.request_lua(script, dict(
            url=self.mockurl('red-green'),
            left=region[0], top=region[1], right=region[2], bottom=region[3],
            scale_method=scale_method,
            width=200,  # 2x smaller image
        ))
        self.assertStatusCode(resp, 200)
        out = resp.json()
        full_img = Image.open(BytesIO(base64.b64decode(out['full'])))
        region_img = Image.open(BytesIO(base64.b64decode(out['shot'])))
        self.assertEqual(region_img.size, (200, 30))
        self.assertImagesEqual(full_img.crop(region).resize((200, 30)),
                               region_img)

    def test_render_region_with_resizing_raster(self):
        self._test_render_region_with_resizing_impl(scale_method='raster')

    def test_render_region_with_resizing_vector(self):
        self._test_render_region_with_resizing_impl(scale_method='vector')

    @pytest.mark.xfail
    def test_render_region_with_tiling(self):
        # Should probably alter red-green page resource so that it can request
        # bigger body size and render_all=1 would produce a tiled image.
        # Otherwise the viewport size is limited by 20000x20000.
        raise NotImplementedError("not implemented yet")

    def test_render_region_with_resizing_and_height_trimming(self):
        script = """
        function main(splash)
            splash:set_viewport_size(1024, 768)
            splash:go(splash.args.url)
            splash:wait(0.1)
            local img = splash:png{region={10, 10, 30, 30}, height=100}
            return {img=img}
        end
        """
        resp = self.request_lua(script, {'url': self.mockurl('red-green')})
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                               "'height' argument is not supported")

    def test_render_region_errors(self):
        out = self.request_lua("""
        function main(splash) splash:png{region='foobar'} end
        """)
        assert out.status_code == 400
        errmsg = out.json()
        assert errmsg['error'] == 400
        assert errmsg['info'] == ("region must be a table containing 4 numbers"
                                  " {left, top, right, bottom} ")


class VersionTest(BaseLuaRenderTest):
    def test_version(self):
        resp = self.request_lua("""
        function main(splash)
            local version = splash:get_version()
            return version.major .. '.' .. version.minor
        end
        """)
        self.assertStatusCode(resp, 200)
        version_min_maj = '.'.join(splash_version.split('.')[:2])
        self.assertEqual(resp.text, version_min_maj)


class EnableDisablePrivateModeTest(BaseLuaRenderTest):
    LOCAL_STORAGE_WORKS_JS = """
    (function () {
        localStorage.setItem("hello", "world of splash");
        return localStorage.getItem("hello") == "world of splash";
    })();
    """

    def test_disable_private_mode(self):
        resp = self.request_lua("""
            function main(splash)
                assert(splash.private_mode_enabled == true)
                splash.private_mode_enabled = false
                assert(splash.private_mode_enabled == false)
                assert(splash:go(splash.args.url))
                assert(splash:runjs(splash.args.js))
                return splash:html()
            end
            """, {
            'url': self.mockurl('jsrender'),
            "js": """
            (function () {
                localStorage.setItem("hello", "world of splash");
                p = document.createElement('p');
                p.textContent = localStorage.getItem("hello");
                document.body.appendChild(p);
            })();
            """
        })
        self.assertStatusCode(resp, 200)
        self.assertIn(u'world of splash', resp.text)

    def test_private_mode_enabled(self):
        resp = self.request_lua("""
            function main(splash)
                assert(splash.private_mode_enabled == true)
                assert(splash:go(splash.args.url))
                return splash:evaljs(splash.args.js)
            end
            """, {
            "js": self.LOCAL_STORAGE_WORKS_JS,
            "url": self.mockurl("jsrender")
        })
        err = self.assertJsonError(resp, 400)
        self.assertEqual(
            err['info']['js_error'],
            "TypeError: null is not an object (evaluating \'localStorage.setItem\')"
        )

    def test_private_mode_disabled(self):
        resp = self.request_lua("""
            function main(splash)
                splash.private_mode_enabled = False
                assert(splash:go(splash.args.url))
                return splash:evaljs(splash.args.js)
            end
            """, {
            "js": self.LOCAL_STORAGE_WORKS_JS,
            "url": self.mockurl("jsrender")
        })
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "True")

    def test_enable_and_disable_private_mode(self):
        resp = self.request_lua("""
            function main(splash)
                assert(splash.private_mode_enabled == true)
                splash.private_mode_enabled = false
                assert(splash.private_mode_enabled == false)
                assert(splash:go(splash.args.url))
                assert(splash:runjs(splash.args.js))
                html1 = splash:html()
                splash.private_mode_enabled = true
                assert(splash:go(splash.args.url))
                html2 = splash:html()
                return {html1=html1, html2=html2}
            end
            """, {
            'url': self.mockurl('jsrender'),
            "js": """
            (function () {
                localStorage.setItem("hello", "world of splash");
                p = document.createElement('p');
                p.textContent = localStorage.getItem("hello");
                document.body.appendChild(p);
            })();
            """
        })
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertIn(u'world of splash', data["html1"])
        self.assertNotIn(u"world of splash", data["html2"])


class PluginsEnabledTest(BaseLuaRenderTest):
    # TODO: test it with a real Flash file
    def test_default_value(self):
        resp = self.request_lua("""
        function main(splash)
            return {enabled=splash.plugins_enabled}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'enabled': defaults.PLUGINS_ENABLED})


class MouseEventsTest(BaseLuaRenderTest):
    def _assert_event_property(self, name, value, resp):
        self.assertIn("{}:{}".format(name, value), resp.text)

    def test_click(self):
        resp = self.request_lua("""
             function main(splash)
                assert(splash:go(splash.args.url))
                get_dimensions = splash:jsfunc([[
                    function () {
                        rect = document.getElementById('button').getBoundingClientRect();
                        return {"x":rect.left, "y": rect.top}
                    }
                ]])
                dimensions = get_dimensions()
                splash:mouse_click(dimensions.x, dimensions.y)
                splash:wait(0.1)
                return splash:html()
            end
            """, {"url": self.mockurl("jsevent?event_type=click")})
        self.assertStatusCode(resp, 200)
        self.assertIn("button", resp.text)
        self.assertNotIn('this must be removed after click', resp.text)
        self._assert_event_property("type", "click", resp)

    def test_click_outside_viewport(self):
        """
        Test clicking on element that is visible only after user scrolls to see it.
        Clicking on element like this is only possible after setting viewport full.
        """
        resp = self.request_lua("""
            function main(splash)
                assert(splash:go(splash.args.url))
                get_dimensions = splash:jsfunc([[
                    function () {
                        rect = document.getElementById('must_scroll_to_see').getBoundingClientRect();
                        return {"x":rect.left, "y": rect.top}
                    }
                ]])
                splash:set_viewport_full()

                dimensions = get_dimensions()
                splash:wait(0.1)
                splash:mouse_click(dimensions.x, dimensions.y)
                -- wait split second to allow event to propagate
                splash:wait(0.1)
                return splash:html()
            end
            """, {"url": self.mockurl("jsevent?event_type=click")})
        self.assertStatusCode(resp, 200)
        self.assertNotIn('this must be removed after click', resp.text)
        self._assert_event_property("type", "click", resp)

    def test_click_outside_viewport_do_scroll(self):
        resp = self.request_lua("""
            function main(splash)
                assert(splash:go(splash.args.url))
                get_dimensions = splash:jsfunc([[
                    function () {
                        rect = document.getElementById('must_scroll_to_see').getBoundingClientRect();
                        return {"x":rect.left, "y": rect.top}
                    }
                ]])
                scroll_down = splash:jsfunc([[
                    function () {
                        window.scrollTo(0, document.body.scrollHeight)
                    }
                ]])

                scroll_down()
                dimensions = get_dimensions()
                splash:wait(0.1)
                splash:mouse_click(dimensions.x, dimensions.y)
                -- wait split second to allow event to propagate
                splash:wait(0.1)
                return splash:html()
            end
            """, {"url": self.mockurl("jsevent?event_type=click")})
        self.assertStatusCode(resp, 200)
        self.assertNotIn('this must be removed after click', resp.text)
        self._assert_event_property("type", "click", resp)

    def test_click_with_bad_arguments(self):
        resp = self.request_lua("""
             function main(splash)
                assert(splash:go(splash.args.url))
                splash:mouse_click(nil, nil)
                splash:wait(0.1)
                return splash:html()
            end

            """, {"url": self.mockurl("jsevent?event_type=click")})
        msg = "coordinate must be a number "
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                               msg)

    def test_hover(self):
        resp = self.request_lua("""
             function main(splash)
                assert(splash:go(splash.args.url))
                get_dimensions = splash:jsfunc([[
                    function () {
                        rect = document.getElementById('button').getBoundingClientRect();
                        return {"x":rect.left, "y": rect.top}
                    }
                ]])
                dimensions = get_dimensions()
                splash:mouse_hover(dimensions.x, dimensions.y)
                splash:wait(0.1)
                return splash:html()
            end
            """, {"url": self.mockurl("jsevent?event_type=mouseover")})
        self.assertStatusCode(resp, 200)
        self.assertIn("button", resp.text)
        self.assertNotIn('this must be removed after hover', resp.text)
        self._assert_event_property("type", "mouseover", resp)

    def test_hover_with_bad_arguments(self):
        resp = self.request_lua("""
                     function main(splash)
                        assert(splash:go(splash.args.url))
                        splash:mouse_hover(nil, nil)
                        splash:wait(0.1)
                        return splash:html()
                    end
                    """, {"url": self.mockurl("jsevent?event_type=mouseover")})

        msg = "coordinate must be a number "
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR, msg)

    def test_mouse_press(self):
        resp = self.request_lua("""
                 function main(splash)
                    assert(splash:go(splash.args.url))
                    get_dimensions = splash:jsfunc([[
                        function () {
                            rect = document.getElementById('button').getBoundingClientRect();
                            return {"x":rect.left, "y": rect.top}
                        }
                    ]])
                    dimensions = get_dimensions()
                    splash:mouse_press(dimensions.x, dimensions.y)
                    splash:wait(0.1)
                    return splash:html()
                end
                """, {"url": self.mockurl("jsevent?event_type=mousedown")})
        self.assertStatusCode(resp, 200)
        self.assertIn("button", resp.text)
        self.assertNotIn('this must be removed', resp.text)
        self._assert_event_property("type", "mousedown", resp)

    def test_press_with_bad_arguments(self):
        resp = self.request_lua("""
                         function main(splash)
                            assert(splash:go(splash.args.url))
                            splash:mouse_press(nil, nil)
                            splash:wait(0.1)
                            return splash:html()
                        end
                        """, {"url": self.mockurl("jsevent?event_type=mousedown")})

        msg = "coordinate must be a number"
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR, msg)

    def test_mouse_release(self):
        resp = self.request_lua("""
                 function main(splash)
                    assert(splash:go(splash.args.url))
                    get_dimensions = splash:jsfunc([[
                        function () {
                            rect = document.getElementById('button').getBoundingClientRect();
                            return {"x":rect.left, "y": rect.top}
                        }
                    ]])
                    dimensions = get_dimensions()
                    splash:mouse_release(dimensions.x, dimensions.y)
                    splash:wait(0.1)
                    return splash:html()
                end
                """, {"url": self.mockurl("jsevent?event_type=mouseup")})
        self.assertStatusCode(resp, 200)
        self.assertIn("button", resp.text)
        self.assertNotIn('this must be removed', resp.text)
        self._assert_event_property("type", "mouseup", resp)

    def test_release_with_bad_arguments(self):
        resp = self.request_lua("""
                         function main(splash)
                            assert(splash:go(splash.args.url))
                            splash:mouse_release(nil, nil)
                            splash:wait(0.1)
                            return splash:html()
                        end
                        """, {"url": self.mockurl("jsevent?event_type=mouseup")})

        msg = "coordinate must be a number"
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR, msg)


class KeyEventsTest(BaseLuaRenderTest):
    def test_send_keys(self):
        resp = self.request_lua("""
             function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                join_inputs = splash:jsfunc([[
                    function () {
                        var inputs = document.getElementsByTagName('input');
                        var values = [];
                        for (var i = 0; i < inputs.length; i++) {
                            values.push(inputs[i].value);
                        }
                        return values.join('|');
                    }
                ]])
                splash:send_keys('<Tab> Hello <Space> World <Tab>')
                splash:send_keys('Foo <Space> Bar')
                splash:send_keys('<Tab>')
                splash:send_keys('Baz')
                assert(splash:wait(0))
                inputs = join_inputs()
                return inputs
            end
            """, {"url": self.mockurl("inputs-page")})
        self.assertStatusCode(resp, 200)
        expected = '|'.join(['Hello World', 'Foo Bar', 'Baz'])
        self.assertEqual(expected, resp.text)

    def test_send_text(self):
        resp = self.request_lua("""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_input = splash:jsfunc([[
                    function () {
                        return document.getElementById('text').value
                    }
                ]])
                splash:send_text('Hello World!')
                assert(splash:wait(0))
                return get_input()
            end
            """, {"url": self.mockurl("focused-input")})
        self.assertStatusCode(resp, 200)
        self.assertEqual('Hello World!', resp.text)

    def test_send_keys_enter_event(self):
        resp = self.request_lua("""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_result = splash:jsfunc([[
                    function () {
                        return document.getElementById('result').innerHTML
                    }
                ]])
                splash:send_keys('<Tab> Username <Tab> Password <Return>')
                assert(splash:wait(0))
                return get_result()
            end
            """, {"url": self.mockurl("form-inputs-event-page")})
        self.assertStatusCode(resp, 200)
        self.assertEqual('Username|Password', resp.text)

    def test_send_text_unicode(self):
        resp = self.request_lua(u"""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_input = splash:jsfunc([[
                    function () {
                        return document.getElementById('text').value
                    }
                ]])
                splash:send_text('Поехали!')
                assert(splash:wait(0))
                return get_input()
            end
            """, {"url": self.mockurl("focused-input")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(u'Поехали!', resp.text)

    def test_send_keys_unicode(self):
        resp = self.request_lua(u"""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_input = splash:jsfunc([[
                    function () {
                        return document.getElementById('text').value
                    }
                ]])
                splash:send_keys('П о е х а л и !')
                assert(splash:wait(0))
                return get_input()
            end
            """, {"url": self.mockurl("focused-input")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(u'Поехали!', resp.text)

    def test_send_text_escaped_newline(self):
        resp = self.request_lua(u"""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_input = splash:jsfunc([[
                    function () {
                        return document.getElementById('text').value
                    }
                ]])
                splash:send_text('Hello World!\\nHello indeed!')
                assert(splash:wait(0))
                return get_input()
            end
            """, {"url": self.mockurl("focused-input")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(u'Hello World!\nHello indeed!', resp.text)

    def test_send_text_w_newline(self):
        # Regardless of the events sent, browser must return these newline /
        # carriage return as just new line.
        resp = self.request_lua(u"""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_input = splash:jsfunc([[
                    function () {
                        return document.getElementById('text').value
                    }
                ]])
                splash:send_text('Hello World!')
                splash:send_keys('<Return> <Enter>')
                splash:send_text('Hello indeed!')
                assert(splash:wait(0))
                return get_input()
            end
            """, {"url": self.mockurl("focused-input")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(u'Hello World!\n\nHello indeed!', resp.text)

    def test_send_keys_complex(self):
        resp = self.request_lua("""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_input = splash:jsfunc([[
                    function () {
                        return document.getElementById('text').value
                    }
                ]])
                splash:send_text('Foo Bar Hello World!')
                splash:send_keys('<Home>')
                for _ = 1, 8, 1 do
                    splash:send_keys('<Delete>')
                end
                splash:send_keys('<End>')
                splash:send_keys('<Left>')
                for _ = 1, 7, 1 do
                    splash:send_keys('<Backspace>')
                end
                assert(splash:wait(0))
                return get_input()
            end
            """, {"url": self.mockurl("focused-input")})
        self.assertStatusCode(resp, 200)
        self.assertEqual(u'Hell!', resp.text)

    def test_send_keys_events_press(self):
        resp = self.request_lua("""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_result = splash:jsfunc([[
                    function () {
                        var res = [];
                        var evs = document.querySelectorAll('ul#output li');
                        for (var i = 0; i < evs.length; i++) {
                            res.push(evs[i].innerHTML);
                        }
                        return res.join(',');
                    }
                ]])
                splash:send_text('Hello World!')
                splash:send_keys('<Return> <Enter> <Delete>')
                assert(splash:wait(0))
                return get_result()
            end
            """, {"url": self.mockurl("key-press-event-logger-page")})
        self.assertStatusCode(resp, 200)
        expected = list(map(lambda c: ord(c), 'Hello World!'))
        # Return, Return, Enter, Delete, Delete
        expected += [ord('\r'), ord('\r'), 127]
        result = list(map(int, resp.text.split(',')))
        self.assertEqual(expected, result)

    def test_send_keys_events_updown(self):
        resp = self.request_lua("""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_result = splash:jsfunc([[
                    function () {
                        var res = [];
                        var evs = document.querySelectorAll('ul#output li');
                        for (var i = 0; i < evs.length; i++) {
                            res.push(evs[i].innerHTML);
                        }
                        return res.join(',');
                    }
                ]])
                splash:send_keys('<Return> <Enter>')
                splash:send_keys('<Space>')
                splash:send_keys('<Tab>')
                splash:send_keys('<Delete>')
                splash:send_keys('<Escape>')
                assert(splash:wait(0))
                return get_result()
            end
            """, {"url": self.mockurl("key-up-down-event-logger-page")})
        self.assertStatusCode(resp, 200)
        expected = [
            13, -13,  # <Return>
            13, -13,  # <Enter>
            32, -32,  # <Space>
            9, -9,  # <Tab>
            46, -46,  # <Delete>
            27, -27  # <Escape>
        ]
        result = list(map(int, resp.text.split(',')))
        self.assertEqual(expected, result)

    def test_send_text_events_updown(self):
        # For now, send text does not send proper keycodes for up/down events
        # defaulting to 0 (key unknown)
        resp = self.request_lua("""
            function main(splash)
                assert(splash:go(splash.args.url))
                assert(splash:wait(0.5))
                get_result = splash:jsfunc([[
                    function () {
                        var res = [];
                        var evs = document.querySelectorAll('ul#output li');
                        for (var i = 0; i < evs.length; i++) {
                            res.push(evs[i].innerHTML);
                        }
                        return res.join(',');
                    }
                ]])
                splash:send_text('Hello World!')
                assert(splash:wait(0))
                return get_result()
            end
            """, {"url": self.mockurl("key-up-down-event-logger-page")})
        self.assertStatusCode(resp, 200)
        expected = []
        for i in range(0, len('Hello World!') * 2):
            prefix = '+' if (i % 2 == 0) else '-'
            expected.append(prefix + '0')
        result = list(resp.text.split(','))
        self.assertEqual(expected, result)

    def test_key_error(self):
        resp = self.request_lua("""
            function main(splash)
                splash:send_keys('<Foobar>')
            end
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                               message="Unknown key")

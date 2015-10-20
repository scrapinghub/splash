# -*- coding: utf-8 -*-
from __future__ import absolute_import
import base64
import json

from splash.exceptions import ScriptError

from .test_execute import BaseLuaRenderTest


class JsonTest(BaseLuaRenderTest):
    def test_json_encode(self):
        resp = self.request_lua("""
        json = require('json')
        function main(splash)
            return {txt=json.encode({x=1})}
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'txt': '{"x": 1}'})

    def test_json_encode_error(self):
        resp = self.request_lua("""
        json = require('json')
        function main(splash)
            return {txt=json.encode({x=function() end})}
        end
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                               message='function objects are not allowed')

    def test_json_decode(self):
        cases = [
            '',
            123,
            {'foo': {'bar': 123}},
            [1,2,3],
            {'foo': [1,2,'bar']},
        ]
        for obj in cases:
            obj_json = json.dumps(obj)
            resp = self.request_lua("""
            json = require('json')
            function main(splash)
                return {res=json.decode(splash.args.obj_json)}
            end
            """, {'obj_json': obj_json})
            self.assertStatusCode(resp, 200)
            self.assertEqual(resp.json(), {'res': obj})

    def test_json_decode_error(self):
        resp = self.request_lua("""
        json = require('json')
        function main(splash)
            return {txt=json.decode("helo{")}
        end
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                               message='No JSON object could be decoded')


class Base64Test(BaseLuaRenderTest):
    def test_b64_encode(self):
        for txt in ["hello", u"привет", ""]:
            resp = self.request_lua("""
            b64 = require('base64')
            function main(splash)
                return {res=b64.encode(splash.args.txt)}
            end
            """, {'txt': txt})
            self.assertStatusCode(resp, 200)
            if not isinstance(txt, bytes):
                txt = txt.encode('utf8')
            self.assertEqual(resp.json(), {'res': base64.b64encode(txt)})

    def test_b64_encode_error(self):
        resp = self.request_lua("""
        base64 = require('base64')
        function main(splash)
            return {txt=base64.encode(123)}
        end
        """)
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                           message='base64.encode argument must be a string')

    def test_b64_decode(self):
        cases = map(base64.b64encode, [
            b'',
            b'foo',
            u'привет'.encode('utf8'),
            u'привет'.encode('cp1251'),
        ])
        for case in cases:
            resp = self.request_lua("""
            base64 = require('base64')
            function main(splash)
                local decoded = base64.decode(splash.args.obj_b64)
                b1, b2, b3, b4 = decoded:byte(1,4)
                return {b1=b1, b2=b2, b3=b3, b4=b4}
            end
            """, {'obj_b64': case})
            self.assertStatusCode(resp, 200)
            expected = bytearray(base64.b64decode(case))
            data = resp.json()
            for i in range(0, 4):
                key = 'b%d' % (i+1)
                if len(expected) > i:
                    self.assertEqual(expected[i], data[key])
                else:
                    self.assertNotIn(key, data)

    def test_b64_decode_error(self):
        resp = self.request_lua("""
        b64 = require('base64')
        function main(splash)
            return {res=b64.decode("xyz")}
        end
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_b64_decode_no_arguments(self):
        resp = self.request_lua("""
        b64 = require('base64')
        function main(splash)
            return {res=b64.decode()}
        end
        """)
        self.assertScriptError(resp, ScriptError.LUA_ERROR)


class TreatAsArrayTest(BaseLuaRenderTest):
    def test_json_encode(self):
        resp = self.request_lua("""
        json = require('json')
        treat = require('treat')
        function main(splash)
            local obj = {"foo", "bar"}
            local arr = treat.as_array({"foo", "bar"})
            return {obj=json.encode(obj), arr=json.encode(arr)}
        end
        """)
        self.assertStatusCode(resp, 200)
        data = resp.json()
        obj = json.loads(data['obj'])
        arr = json.loads(data['arr'])
        self.assertEqual(obj, {"1": "foo", "2": "bar"})
        self.assertEqual(arr, ["foo", "bar"])

    def test_return_main_result(self):
        resp = self.request_lua("""
        treat = require('treat')
        function main(splash)
            return treat.as_array({"foo", "bar"})
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), ["foo", "bar"])

    def test_modify_inplace(self):
        resp = self.request_lua("""
        treat = require('treat')
        function main(splash)
            local obj = {"foo", "bar"}
            treat.as_array(obj)
            return obj
        end
        """)
        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), ["foo", "bar"])

    def test_as_array_not_array(self):
        resp = self.request_lua("""
        treat = require('treat')
        function main(splash)
            return treat.as_array({foo="bar", egg="spam", [1]="baz"})
        end
        """)
        self.assertScriptError(resp, ScriptError.BAD_MAIN_ERROR)

        resp = self.request_lua("""
        treat = require('treat')
        json = require('json')
        function main(splash)
            local res = json.encode(treat.as_array({foo="bar", egg="spam", [1]="baz"}))
            return res
        end
        """)
        self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)

    def test_as_array_not_table(self):
        for obj in ['"foo"', "5.1", "function() end", "", "splash:png()"]:
            resp = self.request_lua("""
            treat = require('treat')
            function main(splash)
                return treat.as_array(%s)
            end
            """ % obj)
            self.assertScriptError(resp, ScriptError.LUA_ERROR,
                                   "argument must be a table")

    def test_as_array_splash(self):
        resp = self.request_lua("""
        treat = require('treat')
        function main(splash)
            return treat.as_array(splash)
        end
        """)
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               "argument must be a table")

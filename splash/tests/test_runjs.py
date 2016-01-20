# -*- coding: utf-8 -*-
from __future__ import absolute_import
import requests
from .test_render import BaseRenderTest
from .utils import SplashServer


CROSS_DOMAIN_JS = """
function getContents(){
    var iframe = document.getElementById('external');
    return iframe.contentDocument.getElementsByTagName('body')[0].innerHTML;
};
getContents();"""


class RunJsTest(BaseRenderTest):
    endpoint = 'render.json'

    def test_simple_js(self):
        js_source = "function test(x){ return x; } test('abc');"
        r = self._runjs_request(js_source).json()
        self.assertEqual(r['script'], "abc")

    def test_js_and_console(self):
        js_source = """function test(x){ return x; }
console.log('some log');
console.log('another log');
test('abc');"""
        params = {'console': '1'}
        r = self._runjs_request(js_source, params=params).json()
        self.assertEqual(r['script'], "abc")
        self.assertEqual(r['console'], ["some log", "another log"])

    def test_js_modify_html(self):
        js_source = """function test(x){ document.getElementById("p1").innerHTML=x; }
test('Changed');"""
        params = {'url': self.mockurl("jsrender")}
        r = self._runjs_request(js_source, endpoint='render.html', params=params)
        self.assertTrue("Before" not in r.text)
        self.assertTrue("Changed" in r.text)

    def test_js_profile(self):
        js_source = """test('abc');"""
        params = {'url': self.mockurl("jsrender"), 'js': 'test'}
        r = self._runjs_request(js_source, params=params).json()
        self.assertEqual(r['script'], "abc")

    def test_js_profile_another_lib(self):
        js_source = """test2('abc');"""
        params = {'url': self.mockurl("jsrender"), 'js': 'test'}
        r = self._runjs_request(js_source, params=params).json()
        self.assertEqual(r['script'], "abcabc")

    def test_js_utf8_lib(self):
        js_source = """console.log(test_utf8('abc')); test_utf8('abc');"""
        params = {'url': self.mockurl("jsrender"), 'js': 'test', 'console': '1'}
        r = self._runjs_request(js_source, params=params).json()
        self.assertEqual(r['script'], u'abc\xae')
        self.assertEqual(r['console'], [u'abc\xae'])

    def test_js_nonexisting(self):
        resp = self._runjs_request("console.log('hello');", params={
            'url': self.mockurl('jsrender'),
            'js': '../../filters'
        })
        data = self.assertJsonError(resp, 400, "BadOption")
        self.assertEqual(data['info']['argument'], 'js')
        self.assertIn("does not exist", data['info']['description'])

    def test_js_external_iframe(self):
        # by default, cross-domain access is disabled, so this does nothing
        params = {'url': self.mockurl("externaliframe")}
        r = self._runjs_request(CROSS_DOMAIN_JS, params=params).json()
        self.assertNotIn('script', r)

    def test_js_incorrect_content_type(self):
        js_source = "function test(x){ return x; } test('abc');"
        headers = {'content-type': 'text/plain'}
        r = self._runjs_request(js_source, headers=headers)
        self.assertStatusCode(r, 415)

    def test_proper_viewport(self):
        js_source = """
            function size() {
                return [window.innerWidth, window.innerHeight].toString();
            }
            size();
            """
        params = {'viewport': '123x234'}
        r = self._runjs_request(js_source, params=params).json()
        self.assertEqual(r['script'], '123,234')

    def test_js_invalid_profile(self):
        js_source = """test('abc');"""
        params = {'url': self.mockurl("jsrender"), 'js': 'not_a_profile'}
        r = self._runjs_request(js_source, params=params)
        self.assertStatusCode(r, 400)


    def _runjs_request(self, js_source, endpoint=None, params=None, headers=None):
        query = {'url': self.mockurl("jsrender"), 'script': 1}
        query.update(params or {})
        req_headers = {'content-type': 'application/javascript'}
        req_headers.update(headers or {})
        return self.post(query, endpoint=endpoint,
                         payload=js_source, headers=req_headers)


class RunJsCrossDomainTest(BaseRenderTest):

    def test_js_external_iframe_cross_domain_enabled(self):
        # cross-domain access should work if we enable it
        with SplashServer(extra_args=['--js-cross-domain-access']) as splash:
            query = {'url': self.mockurl("externaliframe"), 'script': 1}
            headers = {'content-type': 'application/javascript'}
            response = requests.post(
                splash.url("render.json"),
                params=query,
                headers=headers,
                data=CROSS_DOMAIN_JS,
            )
            self.assertEqual(response.json()['script'], u'EXTERNAL\n\n')


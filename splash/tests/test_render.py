# -*- coding: utf-8 -*-
import unittest
import json
import base64
import urllib
from functools import wraps
from cStringIO import StringIO

import pytest
import requests
from PIL import Image
from splash.tests.utils import NON_EXISTING_RESOLVABLE
from splash.tests.utils import SplashServer


def https_only(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            if self.__class__.https_supported:
                func(self, *args, **kwargs)
        except AttributeError:
            func(self, *args, **kwargs)
    return wrapper


def skip_proxy(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            if self.__class__.proxy_test is False:
                func(self, *args, **kwargs)
        except AttributeError:
            func(self, *args, **kwargs)
    return wrapper


class DirectRequestHandler(object):

    render_format = "html"

    def __init__(self, ts):
        self.ts = ts

    @property
    def host(self):
        return "localhost:%s" % self.ts.splashserver.portnum

    def request(self, query, render_format=None, headers=None):
        url, params = self._url_and_params(render_format, query)
        return requests.get(url, params=params, headers=headers)

    def post(self, query, render_format=None, payload=None, headers=None):
        url, params = self._url_and_params(render_format, query)
        return requests.post(url, params=params, data=payload, headers=headers)

    def _url_and_params(self, render_format, query):
        render_format = render_format or self.render_format
        if isinstance(query, dict):
            url = "http://%s/render.%s" % (self.host, render_format)
            params = query
        else:
            url = "http://%s/render.%s?%s" % (self.host, render_format, query)
            params = None
        return url, params


@pytest.mark.usefixtures("class_ts")
@pytest.mark.usefixtures("print_ts_output")
class BaseRenderTest(unittest.TestCase):

    render_format = "html"
    request_handler = DirectRequestHandler
    use_gzip = False

    def setUp(self):
        if self.use_gzip:
            try:
                from twisted.web.server import GzipEncoderFactory
            except ImportError:
                pytest.skip("Gzip support is not available in old Twisted")

    def mockurl(self, path, host='localhost'):
        return self.ts.mockserver.url(path, self.use_gzip, host=host)

    def _get_handler(self):
        handler = self.request_handler(self.ts)
        handler.render_format = self.render_format
        return handler

    def request(self, query, render_format=None, headers=None, **kwargs):
        return self._get_handler().request(query, render_format, headers, **kwargs)

    def post(self, query, render_format=None, payload=None, headers=None, **kwargs):
        return self._get_handler().post(query, render_format, payload, headers, **kwargs)


class _RenderTest(BaseRenderTest):

    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_render_error(self):
        r = self.request({"url": "http://non-existent-host/"})
        self.assertEqual(r.status_code, 502)

    def test_timeout(self):
        r = self.request({"url": self.mockurl("delay?n=10"), "timeout": "0.5"})
        self.assertEqual(r.status_code, 504)

    def test_timeout_out_of_range(self):
        r = self.request({"url": self.mockurl("delay?n=10"), "timeout": "999"})
        self.assertEqual(r.status_code, 400)

    @skip_proxy
    def test_missing_url(self):
        r = self.request({})
        self.assertEqual(r.status_code, 400)
        self.assertTrue("url" in r.text)

    def test_jsalert(self):
        r = self.request({"url": self.mockurl("jsalert"), "timeout": "3"})
        self.assertEqual(r.status_code, 200)

    def test_jsconfirm(self):
        r = self.request({"url": self.mockurl("jsconfirm"), "timeout": "3"})
        self.assertEqual(r.status_code, 200)

    def test_iframes(self):
        r = self.request({"url": self.mockurl("iframes"), "timeout": "3"})
        self.assertEqual(r.status_code, 200)

    def test_wait(self):
        r1 = self.request({"url": self.mockurl("jsinterval")})
        r2 = self.request({"url": self.mockurl("jsinterval")})
        r3 = self.request({"url": self.mockurl("jsinterval"), "wait": "0.2"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r1.content, r2.content)
        self.assertNotEqual(r1.content, r3.content)


class RenderHtmlTest(_RenderTest):

    render_format = "html"

    def test_jsrender(self):
        self._test_jsrender(self.mockurl("jsrender"))

    @https_only
    def test_jsrender_https(self):
        self._test_jsrender(self.ts.mockserver.https_url("jsrender"))

    def _test_jsrender(self, url):
        r = self.request({"url": url})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"].lower(), "text/html; charset=utf-8")
        self.assertTrue("Before" not in r.text)
        self.assertTrue("After" in r.text)

    def test_baseurl(self):
        # first make sure that script.js is served under the right url
        self.assertEqual(404, requests.get(self.mockurl("script.js")).status_code)
        self.assertEqual(200, requests.get(self.mockurl("baseurl/script.js")).status_code)

        # r = self.request("url=http://localhost:8998/baseurl&baseurl=http://localhost:8998/baseurl/")
        r = self.request({
            "url": self.mockurl("baseurl"),
            "baseurl": self.mockurl("baseurl/"),
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Before" not in r.text)
        self.assertTrue("After" in r.text)

    def test_otherdomain(self):
        r = self.request({"url": self.mockurl("iframes")})
        self.assertEqual(r.status_code, 200)
        self.assertTrue('SAME_DOMAIN' in r.text)
        self.assertTrue('OTHER_DOMAIN' in r.text)

    def test_allowed_domains(self):
        r = self.request({'url': self.mockurl('iframes'), 'allowed_domains': 'localhost'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue('SAME_DOMAIN' in r.text)
        self.assertFalse('OTHER_DOMAIN' in r.text)

    def test_viewport(self):
        r = self.request({'url': self.mockurl('jsviewport'), 'viewport': '300x400'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('300x400', r.text)

    def test_nonascii_url(self):
        nonascii_value =  u'тест'.encode('utf8')
        url = self.mockurl('getrequest') + '?param=' + nonascii_value
        r = self.request({'url': url})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            repr(nonascii_value) in r.text or  # direct request
            urllib.quote(nonascii_value) in r.text,  # request in proxy mode
            r.text
        )

    def test_result_encoding(self):
        r1 = requests.get(self.mockurl('cp1251'))
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.encoding, 'windows-1251')
        self.assertTrue(u'проверка' in r1.text)

        r2 = self.request({'url': self.mockurl('cp1251')})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.encoding, 'utf-8')
        self.assertTrue(u'проверка' in r2.text)

    @skip_proxy
    def test_404_get(self):
        self.assertResponse200Get(404)

    @skip_proxy
    def test_403_get(self):
        self.assertResponse200Get(403)

    @skip_proxy
    def test_500_get(self):
        self.assertResponse200Get(500)

    @skip_proxy
    def test_503_get(self):
        self.assertResponse200Get(503)

    def assertResponse200Get(self, code):
        url = self.mockurl('getrequest') + '?code=%d' % code
        r = self.request({'url': url})
        self.assertEqual(r.status_code, 200)
        self.assertIn("GET request", r.text)


class RenderPngTest(_RenderTest):

    render_format = "png"

    def test_ok(self):
        self._test_ok(self.mockurl("jsrender"))

    @https_only
    def test_ok_https(self):
        self._test_ok(self.ts.mockserver.https_url("jsrender"))

    def _test_ok(self, url):
        r = self.request("url=%s" % url)
        self.assertPng(r, width=1024, height=768)

    def test_width(self):
        r = self.request({"url": self.mockurl("jsrender"), "width": "300"})
        self.assertPng(r, width=300)

    def test_width_height(self):
        r = self.request({"url": self.mockurl("jsrender"), "width": "300", "height": "100"})
        self.assertPng(r, width=300, height=100)

    def test_range_checks(self):
        for arg in ('width', 'height'):
            for val in (-1, 99999):
                url = self.mockurl("jsrender")
                r = self.request("url=%s&%s=%d" % (url, arg, val))
                self.assertEqual(r.status_code, 400)

    def test_viewport_full_wait(self):
        r = self.request({'url': self.mockurl("jsrender"), 'viewport': 'full'})
        self.assertEqual(r.status_code, 400)

        r = self.request({'url': self.mockurl("jsrender"), 'viewport': 'full', 'wait': 0.1})
        self.assertEqual(r.status_code, 200)

    def test_viewport_checks(self):
        for viewport in ['99999x1', '1x99999', 'foo', '1xfoo', 'axe', '9000x9000', '-1x300']:
            r = self.request({'url': self.mockurl("jsrender"), 'viewport': viewport})
            self.assertEqual(r.status_code, 400)

    def test_viewport_full(self):
        r = self.request({'url': self.mockurl("tall"), 'viewport': 'full', 'wait': 0.1})
        self.assertPng(r, height=2000)  # 2000px is hardcoded in that html

    def test_images_enabled(self):
        r = self.request({'url': self.mockurl("show-image"), 'viewport': '100x100'})
        self.assertPixelColor(r, 30, 30, (0,0,0,255))

    def test_images_disabled(self):
        r = self.request({'url': self.mockurl("show-image"), 'viewport': '100x100', 'images': 0})
        self.assertPixelColor(r, 30, 30, (255,255,255,255))

    def assertPng(self, response, width=None, height=None):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        img = Image.open(StringIO(response.content))
        self.assertEqual(img.format, "PNG")
        if width is not None:
            self.assertEqual(img.size[0], width)
        if height is not None:
            self.assertEqual(img.size[1], height)
        return img.size

    def assertPixelColor(self, response, x, y, color):
        img = Image.open(StringIO(response.content))
        self.assertEqual(color, img.getpixel((x, y)))


class RenderJsonTest(_RenderTest):

    render_format = 'json'

    def test_jsrender_html(self):
        self.assertSameHtml(self.mockurl("jsrender"))

    @https_only
    def test_jsrender_https_html(self):
        self.assertSameHtml(self.ts.mockserver.https_url("jsrender"))

    def test_jsalert_html(self):
        self.assertSameHtml(self.mockurl("jsalert"), {'timeout': 3})

    def test_jsconfirm_html(self):
        self.assertSameHtml(self.mockurl("jsconfirm"), {'timeout': 3})

    def test_iframes_html(self):
        self.assertSameHtml(self.mockurl("iframes"), {'timeout': 3})

    def test_allowed_domains_html(self):
        self.assertSameHtml(self.mockurl("iframes"), {'allowed_domains': 'localhost'})


    def test_jsrender_png(self):
        self.assertSamePng(self.mockurl("jsrender"))

    @https_only
    def test_jsrender_https_png(self):
        self.assertSamePng(self.ts.mockserver.https_url("jsrender"))

    def test_jsalert_png(self):
        self.assertSamePng(self.mockurl("jsalert"), {'timeout': 3})

    def test_jsconfirm_png(self):
        self.assertSamePng(self.mockurl("jsconfirm"), {'timeout': 3})

    def test_iframes_png(self):
        self.assertSamePng(self.mockurl("iframes"), {'timeout': 3})

    def test_png_size(self):
        self.assertSamePng(self.mockurl("jsrender"), {'width': 100})
        self.assertSamePng(self.mockurl("jsrender"), {'width': 100, 'height': 200})
        self.assertSamePng(self.mockurl("jsrender"),
                           {'width': 100, 'height': 200, 'vwidth': 100, 'vheight': 200})
        self.assertSamePng(self.mockurl("jsrender"),
                           {'vwidth': 100})

    def test_png_size_viewport(self):
        self.assertSamePng(self.mockurl("jsrender"), {'wait': 0.1, 'viewport': 'full'})
        self.assertSamePng(self.mockurl("tall"), {'wait': 0.1, 'viewport': 'full'})

    def test_png_images(self):
        self.assertSamePng(self.mockurl("show-image"), {"viewport": "100x100"})
        self.assertSamePng(self.mockurl("show-image"), {"viewport": "100x100", "images": 0})

    @https_only
    def test_fields_all(self):
        query = {'url': self.ts.mockserver.https_url("iframes"),
                 "html": 1, "png": 1, "iframes": 1}

        res = self.request(query).json()
        self.assertFieldsInResponse(res, ["html", "png", "url", "requestedUrl",
                                          "childFrames", "geometry", "title"])
        frames = res['childFrames']
        self.assertTrue(frames)
        for frame in frames:
            self.assertFieldsInResponse(frame, ["html", "url", "requestedUrl",
                                               "childFrames", "geometry", "title"])
            # no screenshots for individual frames
            self.assertFieldsNotInResponse(frame, ['png'])

    @https_only
    def test_fields_no_html(self):
        # turn off returning HTML
        query = {'url': self.ts.mockserver.https_url("iframes"),
                 'html': 0, 'png': 1, 'iframes': 1}

        res = self.request(query).json()
        self.assertFieldsInResponse(res, ["png", "url", "requestedUrl",
                                          "childFrames", "geometry", "title"])
        self.assertFieldsNotInResponse(res, ['html'])

        # html=0 also turns off html for iframes
        frames = res['childFrames']
        self.assertTrue(frames)
        for frame in frames:
            self.assertFieldsInResponse(frame, ["url", "requestedUrl",
                                                "childFrames", "geometry", "title"])
            self.assertFieldsNotInResponse(frame, ['html', 'png'])

    @https_only
    def test_fields_no_screenshots(self):
        # turn off screenshots
        query = {'url': self.ts.mockserver.https_url("iframes"),
                 'html': 1, 'png': 0, 'iframes': 1}
        res = self.request(query).json()
        self.assertFieldsInResponse(res, ["url", "requestedUrl", "childFrames",
                                          "geometry", "title", "html"])
        self.assertFieldsNotInResponse(res, ["png"])

    @https_only
    def test_fields_no_iframes(self):
        query = {'url': self.ts.mockserver.https_url("iframes"),
                 'html': 1, 'png': 1, 'iframes': 0}
        res = self.request(query).json()
        self.assertFieldsInResponse(res, ["url", "requestedUrl", "geometry",
                                          "title", "html", "png"])
        self.assertFieldsNotInResponse(res, ["childFrames"])

    @https_only
    def test_fields_default(self):
        query = {'url': self.ts.mockserver.https_url("iframes")}
        res = self.request(query).json()
        self.assertFieldsInResponse(res, ["url", "requestedUrl", "geometry",
                                          "title"])
        self.assertFieldsNotInResponse(res, ["childFrames", "html", "png"])

    def test_wait(self):
        # override parent's test to make it aware of render.json endpoint
        r1 = self.request({"url": self.mockurl("jsinterval"), 'html': 1})
        r2 = self.request({"url": self.mockurl("jsinterval"), 'html': 1})
        r3 = self.request({"url": self.mockurl("jsinterval"), 'wait': 0.2, 'html': 1})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r3.status_code, 200)

        html1 = r1.json()['html']
        html2 = r2.json()['html']
        html3 = r3.json()['html']
        self.assertEqual(html1, html2)
        self.assertNotEqual(html1, html3)

    def test_result_encoding(self):
        r = self.request({'url': self.mockurl('cp1251'), 'html': 1})
        self.assertEqual(r.status_code, 200)
        html = r.json()['html']
        self.assertTrue(u'проверка' in html)
        self.assertTrue(u'1251' in html)


    def assertFieldsInResponse(self, res, fields):
        for key in fields:
            self.assertTrue(key in res, "%s is not in response" % key)

    def assertFieldsNotInResponse(self, res, fields):
        for key in fields:
            self.assertTrue(key not in res, "%s is in response" % key)

    def assertSameHtml(self, url, params=None):
        defaults = {'html': 1}
        defaults.update(params or {})
        r1, r2 = self._do_same_requests(url, defaults, 'html')
        html1 = r1.json()['html']
        html2 = r2.text
        self.assertEqual(html1, html2)

    def assertSamePng(self, url, params=None):
        defaults = {'png': 1}
        defaults.update(params or {})
        r1, r2 = self._do_same_requests(url, defaults, 'png')
        png_json = r1.json()['png']
        assert b'\n' not in png_json
        png1 = base64.b64decode(png_json)
        png2 = r2.content
        self.assertEqual(png1, png2)

    def _do_same_requests(self, url, params, other_format):
        query = {'url': url}
        query.update(params or {})
        r1 = self.request(query, render_format='json')
        r2 = self.request(query, render_format=other_format)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        return r1, r2


class RenderJsonHistoryTest(BaseRenderTest):
    render_format = 'json'

    def test_history_simple(self):
        self.assertHistoryUrls(
            {'url': self.mockurl('jsrender')},
            [('jsrender', 200)]
        )

    def test_history_jsredirect(self):
        self.assertHistoryUrls(
            {'url': self.mockurl('jsredirect')},
            [('jsredirect', 200)]
        )

        self.assertHistoryUrls(
            {'url': self.mockurl('jsredirect'), 'wait': 0.2},
            [('jsredirect', 200), ('jsredirect-target', 200)]
        )

    def test_history_metaredirect(self):
        self.assertHistoryUrls(
            {'url': self.mockurl('meta-redirect0'), 'wait': 0.2},
            [('meta-redirect0', 200), ('meta-redirect-target/', 200)]
        )

    def test_history_httpredirect(self):
        self.assertHistoryUrls(
            {'url': self.mockurl('http-redirect?code=302')},
            [('getrequest?http_code=302', 200)]
        )

    def test_history_iframes(self):
        self.assertHistoryUrls({'url': self.mockurl('iframes')}, [('iframes', 200)])

    def test_history_status_codes(self):
        for code in [404, 403, 400, 500, 503]:
            url = self.mockurl('getrequest') + '?code=%d' % code
            self.assertHistoryUrls({'url': url}, [(url, code)], full_urls=True)


    def assertHistoryUrls(self, query, urls_and_codes, full_urls=False):
        query['history'] = 1
        resp = self.request(query)
        history = resp.json()['history']
        assert len(history) == len(urls_and_codes), history

        server_addr = self.mockurl('')

        for entry, (url, code) in zip(history, urls_and_codes):
            response_url = entry["request"]["url"]
            assert response_url.startswith(server_addr), (response_url, server_addr)
            if not full_urls:
                response_url = response_url[len(server_addr):]
            self.assertEqual(response_url, url)
            self.assertEqual(entry["response"]["status"], code)

        return history


class IframesRenderTest(BaseRenderTest):
    render_format = 'json'

    def test_basic(self):
        self.assertIframesText('IFRAME_1_OK')

    def test_js_iframes(self):
        self.assertIframesText('IFRAME_2_OK')

    def test_delayed_js_iframes(self):
        self.assertNoIframesText('IFRAME_3_OK', {'wait': 0.0})
        self.assertIframesText('IFRAME_3_OK', {'wait': 0.5})

    def test_onload_iframes(self):
        self.assertIframesText('IFRAME_4_OK')

    def test_document_write_iframes(self):
        self.assertIframesText('IFRAME_5_OK')

    def test_nested_iframes(self):
        self.assertIframesText('IFRAME_6_OK')


    def assertIframesText(self, text, params=None):
        data = self._iframes_request(params)
        self.assertTrue(self._text_is_somewhere(data, text))

    def assertNoIframesText(self, text, params=None):
        data = self._iframes_request(params)
        self.assertFalse(self._text_is_somewhere(data, text))

    def _text_is_somewhere(self, result, text):
        if text in result['html']:
            return True
        return any(self._text_is_somewhere(child, text)
                   for child in result['childFrames'])

    def _iframes_request(self, params):
        query = {'url': self.ts.mockserver.https_url("iframes"),
                 'iframes': 1, 'html': 1}
        query.update(params or {})
        return self.request(query).json()



@pytest.mark.usefixtures("class_ts")
@pytest.mark.usefixtures("print_ts_output")
class TestTestSetup(unittest.TestCase):

    def test_mockserver_works(self):
        r = requests.get(self.ts.mockserver.url("jsrender", gzip=False))
        self.assertEqual(r.status_code, 200)

    def test_mockserver_https_works(self):
        r = requests.get(self.ts.mockserver.https_url("jsrender"), verify=False)
        self.assertEqual(r.status_code, 200)

    def test_splashserver_works(self):
        r = requests.get('http://localhost:%s/debug' % self.ts.splashserver.portnum)
        self.assertEqual(r.status_code, 200)

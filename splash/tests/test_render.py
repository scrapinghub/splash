# -*- coding: utf-8 -*-
from array import array
import unittest
import base64
from functools import wraps
from io import BytesIO

import pytest
import requests
from PIL import Image, ImageChops
from six.moves.urllib import parse as urlparse

from splash import defaults
from splash.qtutils import qt_551_plus
from splash.utils import truncated
from splash.tests.utils import NON_EXISTING_RESOLVABLE, SplashServer


def https_only(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            if self.__class__.https_supported:
                func(self, *args, **kwargs)
        except AttributeError:
            func(self, *args, **kwargs)
    return wrapper


class DirectRequestHandler(object):

    endpoint = "render.html"

    def __init__(self, ts):
        self.ts = ts

    @property
    def host(self):
        return "localhost:%s" % self.ts.splashserver.portnum

    def request(self, query, endpoint=None, headers=None):
        url, params = self._url_and_params(endpoint, query)
        return requests.get(url, params=params, headers=headers)

    def post(self, query, endpoint=None, payload=None, headers=None):
        url, params = self._url_and_params(endpoint, query)
        return requests.post(url, params=params, data=payload, headers=headers)

    def _url_and_params(self, endpoint, query):
        endpoint = endpoint if endpoint is not None else self.endpoint
        if isinstance(query, dict):
            url = "http://%s/%s" % (self.host, endpoint)
            params = query
        else:
            url = "http://%s/%s?%s" % (self.host, endpoint, query)
            params = None
        return url, params


@pytest.mark.usefixtures("class_ts")
class BaseRenderTest(unittest.TestCase):

    endpoint = "render.html"
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
        handler.endpoint = self.endpoint
        return handler

    def request(self, query, endpoint=None, headers=None, **kwargs):
        return self._get_handler().request(query, endpoint, headers, **kwargs)

    def post(self, query, endpoint=None, payload=None, headers=None, **kwargs):
        return self._get_handler().post(query, endpoint, payload, headers, **kwargs)

    def assertStatusCode(self, response, code):
        msg = (response.status_code, truncated(response.text, 1000))
        self.assertEqual(response.status_code, code, msg)

    def assertJsonError(self, response, code, error_type=None):
        self.assertStatusCode(response, code)
        data = response.json()
        self.assertEqual(data['error'], code)
        if error_type is not None:
            self.assertEqual(data['type'], error_type)
        return data

    def assertBadArgument(self, response, argname):
        data = self.assertJsonError(response, 400, "BadOption")
        self.assertEqual(data['info']['argument'], argname)

    def assertPng(self, response, width=None, height=None):
        self.assertStatusCode(response, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        img = Image.open(BytesIO(response.content))
        self.assertEqual(img.format, "PNG")
        if width is not None:
            self.assertEqual(img.size[0], width)
        if height is not None:
            self.assertEqual(img.size[1], height)
        return img

    def assertJpeg(self, response, width=None, height=None):
        self.assertStatusCode(response, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        img = Image.open(BytesIO(response.content))
        self.assertEqual(img.format, "JPEG")
        if width is not None:
            self.assertEqual(img.size[0], width)
        if height is not None:
            self.assertEqual(img.size[1], height)
        return img

    def assertPixelColor(self, response, x, y, color):
        img = Image.open(BytesIO(response.content))
        self.assertEqual(color, img.getpixel((x, y)))

    COLOR_NAMES = ('red', 'green', 'blue', 'alpha')

    def assertBoxColor(self, response, box, etalon):
        img = Image.open(BytesIO(response.content))
        if img.format == 'PNG':
            assert len(etalon) == 4  # RGBA components
        elif img.format == 'JPEG':
            assert len(etalon) == 3  # RGB components
        else:
            raise TypeError('Unexpected image format {}'.format(img.format))
        extrema = img.crop(box).getextrema()
        for (color_name, (min_val, max_val)) in zip(self.COLOR_NAMES, extrema):
            self.assertEqual(
                min_val, max_val,
                "Selected region does not have same values in %s component:"
                "%s -> %s" % (color_name, min_val, max_val))
        color = tuple(e[0] for e in extrema)
        self.assertEqual(color, etalon,
                         "Region color (%s) doesn't match the etalon (%s)" %
                         (color, etalon))

    def assertImagesEqual(self, img1, img2):
        diffbox = ImageChops.difference(img1, img2).getbbox()
        self.assertIsNone(diffbox, ("Images differ in region %s" % (diffbox,)))


class Base(object):
    # a hack to skip running of a base RenderTest

    class RenderTest(BaseRenderTest):

        @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
        def test_render_error(self):
            r = self.request({"url": "http://non-existent-host/"})
            self.assertStatusCode(r, 502)

        def test_timeout(self):
            r = self.request({"url": self.mockurl("delay?n=10"), "timeout": "0.5"})
            self.assertStatusCode(r, 504)

        def test_timeout_out_of_range(self):
            r = self.request({"url": self.mockurl("delay?n=10"), "timeout": "999"})
            self.assertStatusCode(r, 400)

        def test_missing_url(self):
            r = self.request({})
            self.assertStatusCode(r, 400)
            self.assertTrue("url" in r.text)

        def test_jsalert(self):
            r = self.request({"url": self.mockurl("jsalert"), "timeout": "3"})
            self.assertStatusCode(r, 200)

        def test_jsconfirm(self):
            r = self.request({"url": self.mockurl("jsconfirm"), "timeout": "3"})
            self.assertStatusCode(r, 200)

        def test_iframes(self):
            r = self.request({"url": self.mockurl("iframes"), "timeout": "3"})
            self.assertStatusCode(r, 200)

        def test_wait(self):
            r1 = self.request({"url": self.mockurl("jsinterval")})
            r2 = self.request({"url": self.mockurl("jsinterval")})
            r3 = self.request({"url": self.mockurl("jsinterval"), "wait": "0.2"})
            self.assertStatusCode(r1, 200)
            self.assertStatusCode(r2, 200)
            self.assertStatusCode(r3, 200)
            self.assertEqual(r1.content, r2.content)
            self.assertNotEqual(r1.content, r3.content)

        def test_invalid_status_code_message(self):
            r = self.request({'url': self.mockurl("bad-status-code-message"),
                              'timeout': "3"})
            self.assertStatusCode(r, 200)

        def test_invalid_wait(self):
            for wait in ['foo', '11', '11.0']:
                r = self.request({'url': self.mockurl("jsrender"),
                                  'wait': wait})
                self.assertStatusCode(r, 400)

        @pytest.mark.skipif(
            not qt_551_plus(),
            reason="resource_timeout doesn't work in Qt5 < 5.5.1. See issue #269 for details."
        )
        def test_resource_timeout(self):
            resp = self.request({
                'url': self.mockurl("show-image?n=10"),
                'timeout': "3",
                'resource_timeout': "0.5",
            })
            self.assertStatusCode(resp, 200)

        @pytest.mark.skipif(
            not qt_551_plus(),
            reason="resource_timeout doesn't work in Qt5 < 5.5.1. See issue #269 for details."
        )
        def test_resource_timeout_abort_first(self):
            resp = self.request({
                'url': self.mockurl("slow.gif?n=3"),
                'resource_timeout': "0.5",
            })
            self.assertStatusCode(resp, 502)


class RenderHtmlTest(Base.RenderTest):

    endpoint = "render.html"

    def test_jsrender(self):
        self._test_jsrender(self.mockurl("jsrender"))

    @https_only
    def test_jsrender_https(self):
        self._test_jsrender(self.ts.mockserver.https_url("jsrender"))

    def _test_jsrender(self, url):
        r = self.request({"url": url})
        self.assertStatusCode(r, 200)
        self.assertEqual(r.headers["content-type"].lower(), "text/html; charset=utf-8")
        self.assertNotIn("Before", r.text)
        self.assertIn("After", r.text)

    def test_baseurl(self):
        # first make sure that script.js is served under the right url
        self.assertEqual(404, requests.get(self.mockurl("script.js")).status_code)
        self.assertEqual(200, requests.get(self.mockurl("baseurl/script.js")).status_code)

        # r = self.request("url=http://localhost:8998/baseurl&baseurl=http://localhost:8998/baseurl/")
        r = self.request({
            "url": self.mockurl("baseurl"),
            "baseurl": self.mockurl("baseurl/"),
        })
        self.assertStatusCode(r, 200)
        self.assertNotIn("Before", r.text)
        self.assertIn("After", r.text)

    def test_otherdomain(self):
        r = self.request({"url": self.mockurl("iframes")})
        self.assertStatusCode(r, 200)
        self.assertIn('SAME_DOMAIN', r.text)
        self.assertIn('OTHER_DOMAIN', r.text)

    def test_allowed_domains(self):
        r = self.request({'url': self.mockurl('iframes'), 'allowed_domains': 'localhost'})
        self.assertStatusCode(r, 200)
        self.assertIn('SAME_DOMAIN', r.text)
        self.assertNotIn('OTHER_DOMAIN', r.text)

    def test_viewport(self):
        r = self.request({'url': self.mockurl('jsviewport'), 'viewport': '300x400'})
        self.assertStatusCode(r, 200)
        self.assertIn('300x400', r.text)

    def test_nonascii_url(self):
        nonascii_value =  u'тест'
        url = self.mockurl('getrequest') + '?param=' + nonascii_value
        r = self.request({'url': url})
        self.assertStatusCode(r, 200)
        self.assertIn(repr(nonascii_value.encode('utf-8')), r.text)

    def test_path_encoding(self):
        r = self.request({'url': self.mockurl(u'echourl/例/')})
        self.assertTrue('/echourl/%E4%BE%8B' in r.text)

        r = self.request({'url': self.mockurl(u'echourl/%E4%BE%8B/')})
        self.assertTrue('/echourl/%E4%BE%8B' in r.text)

    def test_result_encoding(self):
        r1 = requests.get(self.mockurl('cp1251'))
        self.assertStatusCode(r1, 200)
        self.assertEqual(r1.encoding, 'windows-1251')
        self.assertIn(u'проверка', r1.text)

        r2 = self.request({'url': self.mockurl('cp1251')})
        self.assertStatusCode(r2, 200)
        self.assertEqual(r2.encoding, 'utf-8')
        self.assertIn(u'проверка', r2.text)

    def test_404_get(self):
        self.assertResponse200Get(404)

    def test_403_get(self):
        self.assertResponse200Get(403)

    def test_500_get(self):
        self.assertResponse200Get(500)

    def test_503_get(self):
        self.assertResponse200Get(503)

    def test_cookies_perserved_after_js_redirect(self):
        self.assertCookiesPreserved(use_js=False)

    def test_js_cookies_perserved_after_js_redirect(self):
        self.assertCookiesPreserved(use_js=True)

    def test_cookies_are_not_shared(self):
        self.assertCookiesNotShared(use_js=False)

    def test_js_cookies_are_not_shared(self):
        self.assertCookiesNotShared(use_js=True)

    def assertCookiesPreserved(self, use_js):
        use_js = "true" if use_js else ""
        get_cookie_url = self.mockurl("get-cookie?key=foo")
        q = urlparse.urlencode({
            "key": "foo",
            "value": "bar",
            "next": get_cookie_url,
            "use_js": use_js,
        })
        url = self.mockurl("set-cookie?%s" % q)
        resp = self.request({"url": url, "wait": "0.2"})
        self.assertStatusCode(resp, 200)
        self.assertIn("bar", resp.text)

    def assertCookiesNotShared(self, use_js):
        use_js = "true" if use_js else ""
        url = self.mockurl("set-cookie?key=egg&value=spam&use_js=%s" % use_js)
        resp = self.request({"url": url})
        self.assertStatusCode(resp, 200)
        self.assertIn("ok", resp.text)

        resp2 = self.request({"url": self.mockurl("get-cookie?key=egg")})
        self.assertStatusCode(resp2, 200)
        self.assertNotIn("spam", resp2.text)

    def assertResponse200Get(self, code):
        url = self.mockurl('getrequest') + '?code=%d' % code
        r = self.request({'url': url})
        self.assertStatusCode(r, 200)
        self.assertIn("GET request", r.text)


class RenderPngTest(Base.RenderTest):

    endpoint = "render.png"

    def test_ok(self):
        self._test_ok(self.mockurl("jsrender"))

    @https_only
    def test_ok_https(self):
        self._test_ok(self.ts.mockserver.https_url("jsrender"))

    def _test_ok(self, url):
        r = self.request({"url": url})
        w, h = map(int, defaults.VIEWPORT_SIZE.split('x'))
        self.assertPng(r, width=w, height=h)

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
                r = self.request({"url": url, arg: val})
                self.assertStatusCode(r, 400)

    def test_viewport_full_wait(self):
        r = self.request({'url': self.mockurl("jsrender"), 'viewport': 'full'})
        self.assertStatusCode(r, 400)
        r = self.request({'url': self.mockurl("jsrender"), 'render_all': 1})
        self.assertStatusCode(r, 400)

        r = self.request({'url': self.mockurl("jsrender"), 'viewport': 'full', 'wait': '0.1'})
        self.assertStatusCode(r, 200)
        r = self.request({'url': self.mockurl("jsrender"), 'render_all': 1, 'wait': '0.1'})
        self.assertStatusCode(r, 200)

    def test_viewport_invalid(self):
        for viewport in ['foo', '1xfoo', 'axe', '-1x300']:
            r = self.request({'url': self.mockurl("jsrender"), 'viewport': viewport})
            self.assertStatusCode(r, 400)

    def test_viewport_out_of_bounds(self):
        for viewport in ['99999x1', '1x99999', '9000x9000']:
            r = self.request({'url': self.mockurl("jsrender"), 'viewport': viewport})
            self.assertStatusCode(r, 400)

    def test_viewport_full(self):
        r = self.request({'url': self.mockurl("tall"), 'viewport': 'full', 'wait': '0.1'})
        self.assertPng(r, height=2000)  # 2000px is hardcoded in that html

    def test_render_all(self):
        r = self.request({'url': self.mockurl("tall"), 'render_all': 1, 'wait': '0.1'})
        self.assertPng(r, height=2000)  # 2000px is hardcoded in that html

    def test_render_all_with_viewport(self):
        r = self.request({'url': self.mockurl("tall"), 'viewport': '2000x1000',
                          'render_all': 1, 'wait': '0.1'})
        self.assertPng(r, width=2000, height=2000)

    def test_images_enabled(self):
        r = self.request({'url': self.mockurl("show-image"), 'viewport': '100x100'})
        self.assertPixelColor(r, 30, 30, (0, 0, 0, 255))

    def test_images_disabled(self):
        r = self.request({'url': self.mockurl("show-image"), 'viewport': '100x100', 'images': 0})
        self.assertPixelColor(r, 30, 30, (255, 255, 255, 255))

    def test_very_long_green_page(self):
        r = self.request({'url': self.mockurl("very-long-green-page"),
                          'render_all': 1, 'wait': '0.01', 'viewport': '50x1024'})
        self.assertPng(r, height=60000)  # hardcoded in the html
        self.assertPixelColor(r, 0, 59999, (0x00, 0xFF, 0x77, 0xFF))

    def test_extra_height_doesnt_leave_garbage_when_using_full_render(self):
        r = self.request({'url': self.mockurl('tall'), 'viewport': '100x100',
                          'height': 1000})
        self.assertPng(r, height=1000)
        # Ensure that the extra pixels at the bottom are transparent.
        self.assertBoxColor(r, (0, 100, 100, 1000), (0, 0, 0, 0))

    def vertical_split_is_sharp(self, img):
        width, height = img.size
        left = (0, 0, width // 2, height)
        right = (width // 2, 0, width, height)
        left_extrema = img.crop(left).getextrema()
        right_extrema = img.crop(right).getextrema()
        return (all(e_min == e_max for e_min, e_max in left_extrema) and
                all(e_min == e_max for e_min, e_max in right_extrema))

    def test_invalid_scale_method(self):
        for method in ['foo', '1', '']:
            r = self.request({'url': self.mockurl("jsrender"),
                              'scale_method': method})
            self.assertStatusCode(r, 400)

    def test_scale_method_raster_produces_blurry_split(self):
        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '100x100', 'width': 200,
                          'scale_method': 'raster'})
        img = self.assertPng(r, width=200, height=200)
        self.assertFalse(self.vertical_split_is_sharp(img),
                         "Split is not blurry")

    def test_scale_method_vector_produces_sharp_split(self):
        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '100x100', 'width': 200,
                          'scale_method': 'vector'})
        img = self.assertPng(r, width=200, height=200)
        self.assertTrue(self.vertical_split_is_sharp(img),
                        "Split is not sharp")


class RenderPngScalingAndCroppingTest(BaseRenderTest):
    endpoint = "render.png"

    RED, GREEN = (255, 0, 0, 255), (0, 255, 0, 255)

    def assertHalfRedHalfGreen(self, r, width, height, delta=5):
        self.assertPng(r, width=width, height=height)
        self.assertBoxColor(r, (0, 0, width // 2 - delta, height),
                            self.RED)
        self.assertBoxColor(r, (width // 2 + delta, 0, width, height),
                            self.GREEN)

    def test_assert_box_color_on_red_green_page(self):
        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '1000x1000'})
        self.assertHalfRedHalfGreen(r, 1000, 1000, delta=0)

    def test_width_parameter_scales_the_image_full_raster(self):
        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '1000x1000', 'width': 200,
                          'scale_method': 'raster'})
        self.assertHalfRedHalfGreen(r, 200, 200, delta=2)

        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '100x100', 'width': 200,
                          'scale_method': 'raster'})
        self.assertHalfRedHalfGreen(r, 200, 200, delta=2)

    def test_width_parameter_scales_the_image_full_vector(self):
        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '1000x1000', 'width': 200,
                          'scale_method': 'vector'})
        self.assertHalfRedHalfGreen(r, 200, 200, delta=0)

        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '100x100', 'width': 200,
                          'scale_method': 'vector'})
        self.assertHalfRedHalfGreen(r, 200, 200, delta=0)

    @pytest.mark.xfail(reason="""
Tiling is enabled in raster mode when any dimension of the viewport reaches
32768, whereas as of now there's a hard limit of 20000 placed in defaults.py
""")
    def test_width_parameter_scales_the_image_tiled_raster(self):
        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '400x33000', 'width': 200,
                          'scale_method': 'raster'})
        self.assertHalfRedHalfGreen(r, 200, 16500, delta=2)

        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '100x33000', 'width': 200})
        self.assertHalfRedHalfGreen(r, 200, 66000, delta=2)

    def test_width_parameter_scales_the_image_tiled_vector(self):
        # Disabled for similar reason as above: tiling in vector mode is
        # enabled when any dimension of the image exceeds 32768, which means
        # that one needs even more to test if downscaling produces a nice
        # equipartitioned image.  Alas, no dimension can exceed 20k.
        #
        # r = self.request({'url': self.mockurl('red-green'),
        #                   'viewport': '400x33000', 'width': 200,
        #                   'scale_method': 'vector'})
        # self.assertHalfRedHalfGreen(r, 200, 16500, delta=2)

        r = self.request({'url': self.mockurl('red-green'),
                          'viewport': '100x16500', 'width': 200,
                          'scale_method': 'vector'})
        self.assertHalfRedHalfGreen(r, 200, 33000, delta=0)

    def test_height_parameter_is_equivalent_to_cropping(self):
        query0 = {'url': self.mockurl('rgb-stripes'), 'width': 99,
                  'viewport': '10x10'}
        r = self.request(query0)
        full_img = self.assertPng(r, width=99, height=99)

        for height in (1, 5, 10, 45, 46, 47, 98, 99, 100, 110):
            query = query0.copy()
            query['height'] = height
            r = self.request(query)
            img = self.assertPng(r, width=99, height=height)
            self.assertImagesEqual(full_img.crop((0, 0, 99, height)), img)


class RenderJsonTest(Base.RenderTest):

    endpoint = 'render.json'

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
        self.assertSamePng(self.mockurl("jsrender"), {'wait': '0.1', 'viewport': 'full'})
        self.assertSamePng(self.mockurl("tall"), {'wait': '0.1', 'viewport': 'full'})

    def test_png_images(self):
        self.assertSamePng(self.mockurl("show-image"), {"viewport": "100x100"})
        self.assertSamePng(self.mockurl("show-image"), {"viewport": "100x100", "images": 0})

    def test_png_scale_method(self):
        self.assertSamePng(self.mockurl("red-green"),
                           {"viewport": "100x100", "width": 200,
                            "scale_method": "raster"})
        self.assertSamePng(self.mockurl("red-green"),
                           {"viewport": "100x100", "width": 200,
                            "scale_method": "vector"})

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
        r3 = self.request({"url": self.mockurl("jsinterval"), 'wait': '0.2', 'html': 1})
        self.assertStatusCode(r1, 200)
        self.assertStatusCode(r2, 200)
        self.assertStatusCode(r3, 200)

        html1 = r1.json()['html']
        html2 = r2.json()['html']
        html3 = r3.json()['html']
        self.assertEqual(html1, html2)
        self.assertNotEqual(html1, html3)

    def test_result_encoding(self):
        r = self.request({'url': self.mockurl('cp1251'), 'html': 1})
        self.assertStatusCode(r, 200)
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
        assert '\n' not in png_json
        png1 = base64.b64decode(png_json)
        png2 = r2.content
        self.assertEqual(png1, png2)

    def _do_same_requests(self, url, params, other_format):
        query = {'url': url}
        query.update(params or {})
        r1 = self.request(query, endpoint='render.json')
        r2 = self.request(query, endpoint='render.' + other_format)
        self.assertStatusCode(r1, 200)
        self.assertStatusCode(r2, 200)
        return r1, r2


class RenderVectorPngTest(RenderPngTest):
    def request(self, query, *args, **kwargs):
        query.setdefault('scale_method', 'vector')
        return super(RenderVectorPngTest, self).request(query, *args, **kwargs)


class RenderJsonHistoryTest(BaseRenderTest):
    endpoint = 'render.json'

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
            {'url': self.mockurl('jsredirect'), 'wait': '0.2'},
            [('jsredirect', 200), ('jsredirect-target', 200)]
        )

    def test_history_metaredirect(self):
        self.assertHistoryUrls(
            {'url': self.mockurl('meta-redirect0'), 'wait': '0.2'},
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
    endpoint = 'render.json'

    def test_basic(self):
        self.assertIframesText('IFRAME_1_OK')

    def test_js_iframes(self):
        self.assertIframesText('IFRAME_2_OK')

    def test_delayed_js_iframes(self):
        self.assertNoIframesText('IFRAME_3_OK', {'wait': '0.0'})
        self.assertIframesText('IFRAME_3_OK', {'wait': '0.5'})

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


class CommandLineOptionsTest(BaseRenderTest):

    def test_max_timeout(self):
        with SplashServer(extra_args=['--max-timeout=0.1']) as splash:
            r1 = requests.get(
                url=splash.url("render.html"),
                params={
                    'url': self.mockurl("delay?n=1"),
                    'timeout': '0.2',
                },
            )
            self.assertStatusCode(r1, 400)

            r2 = requests.get(
                url=splash.url("render.html"),
                params={
                    'url': self.mockurl("delay?n=1"),
                    'timeout': '0.1',
                },
            )
            self.assertStatusCode(r2, 504)

            r3 = requests.get(
                url=splash.url("render.html"),
                params={
                    'url': self.mockurl("delay?n=1")
                },
            )
            self.assertStatusCode(r3, 504)

            r4 = requests.get(
                url=splash.url("render.html"),
                params={
                    'url': self.mockurl("")
                },
            )
            self.assertStatusCode(r4, 200)


@pytest.mark.usefixtures("class_ts")
class TestTestSetup(unittest.TestCase):

    def test_mockserver_works(self):
        r = requests.get(self.ts.mockserver.url("jsrender", gzip=False))
        self.assertEqual(r.status_code, 200)

    def test_mockserver_https_works(self):
        r = requests.get(self.ts.mockserver.https_url("jsrender"), verify=False)
        self.assertEqual(r.status_code, 200)

    def test_splashserver_works(self):
        r = requests.get('http://localhost:%s/_debug' % self.ts.splashserver.portnum)
        self.assertEqual(r.status_code, 200)

    def test_splashserver_pings(self):
        r = requests.get('http://localhost:%s/_ping' % self.ts.splashserver.portnum)
        self.assertEqual(r.status_code, 200)


class RenderJpegTest(Base.RenderTest):

    endpoint = "render.jpeg"

    def test_ok(self):
        self._test_ok(self.mockurl("jsrender"))

    @https_only
    def test_ok_https(self):
        self._test_ok(self.ts.mockserver.https_url("jsrender"))

    def _test_ok(self, url):
        r = self.request({"url": url})
        w, h = map(int, defaults.VIEWPORT_SIZE.split('x'))
        self.assertJpeg(r, width=w, height=h)

    def test_width(self):
        r = self.request({"url": self.mockurl("jsrender"), "width": "300"})
        self.assertJpeg(r, width=300)

    def test_width_height(self):
        r = self.request({"url": self.mockurl("jsrender"), "width": "300", "height": "100"})
        self.assertJpeg(r, width=300, height=100)

    def test_width_height_high_quality(self):
        r = self.request({
            "url": self.mockurl("jsrender"),
            "width": "1500",
            "height": "500",
            "quality": "90"
        })
        img = self.assertJpeg(r, width=1500, height=500)
        # There's no way to detect exact quality number from the response, but
        # quality number is reflected in quantization tables, so we can check them
        self.assertEqual(img.quantization[0], array('b', [
            3, 2, 2, 3, 2, 2, 3, 3, 3, 3, 4, 3, 3, 4, 5, 8, 5, 5, 4, 4,
            5, 10, 7, 7, 6, 8, 12, 10, 12, 12, 11, 10, 11, 11, 13, 14,
            18, 16, 13, 14, 17, 14, 11, 11,  16, 22, 16, 17, 19, 20,
            21, 21, 21, 12, 15, 23, 24, 22, 20, 24, 18, 20, 21, 20
        ]))
        # There's no way to detect exact quality number from the response, but
        # quality number is reflected in quantization tables, so we can check them
        self.assertEqual(img.quantization[1], array('b', [
            3, 4, 4, 5, 4, 5, 9, 5, 5, 9, 20, 13, 11, 13, 20, 20, 20, 20,
            20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20,
            20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20,
            20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20
        ]))

    def test_width_height_low_quality(self):
        r = self.request({
            "url": self.mockurl("jsrender"),
            "width": "1500",
            "height": "500",
            "quality": "10"
        })
        img = self.assertJpeg(r, width=1500, height=500)
        # There's no way to detect exact quality number from the response, but
        # quality number is reflected in quantization tables, so we can check them
        self.assertEqual(img.quantization[0].tostring(), array('b', [
            80, 55, 60, 70, 60, 50, 80, 70, 65, 70, 90, 85, 80, 95, 120, -56, -126, 120,
            110, 110, 120, -11, -81, -71, -111, -56, -1, -1, -1, -1, -1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1, -1, -1, -1, -1, -1
        ]).tostring())

        # There's no way to detect exact quality number from the response, but
        # quality number is reflected in quantization tables, so we can check them
        self.assertEqual(img.quantization[1].tostring(), array('b', [
            85, 90, 90, 120, 105, 120, -21, -126, -126, -21, -1, -1, -1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1, -1, -1, -1, -1
        ]).tostring())

    def test_range_checks(self):
        for arg in ('width', 'height'):
            for val in (-1, 99999):
                url = self.mockurl("jsrender")
                r = self.request({"url": url, arg: val})
                self.assertStatusCode(r, 400)

    def test_viewport_full_wait(self):
        r = self.request({'url': self.mockurl("jsrender"), 'viewport': 'full'})
        self.assertStatusCode(r, 400)
        r = self.request({'url': self.mockurl("jsrender"), 'render_all': 1})
        self.assertStatusCode(r, 400)

        r = self.request({'url': self.mockurl("jsrender"), 'viewport': 'full', 'wait': '0.1'})
        self.assertStatusCode(r, 200)
        self.assertJpeg(r)
        r = self.request({'url': self.mockurl("jsrender"), 'render_all': 1, 'wait': '0.1'})
        self.assertStatusCode(r, 200)
        self.assertJpeg(r)

    def test_viewport_invalid(self):
        for viewport in ['foo', '1xfoo', 'axe', '-1x300']:
            r = self.request({'url': self.mockurl("jsrender"), 'viewport': viewport})
            self.assertStatusCode(r, 400)

    def test_viewport_out_of_bounds(self):
        for viewport in ['99999x1', '1x99999', '9000x9000']:
            r = self.request({'url': self.mockurl("jsrender"), 'viewport': viewport})
            self.assertStatusCode(r, 400)

    def test_viewport_full(self):
        r = self.request({'url': self.mockurl("tall"), 'viewport': 'full', 'wait': '0.1'})
        self.assertJpeg(r, height=2000)  # 2000px is hardcoded in that html

    def test_render_all(self):
        r = self.request({'url': self.mockurl("tall"), 'render_all': 1, 'wait': '0.1'})
        self.assertJpeg(r, height=2000)  # 2000px is hardcoded in that html

    def test_render_all_with_viewport(self):
        r = self.request({'url': self.mockurl("tall"), 'viewport': '2000x1000',
                          'render_all': 1, 'wait': '0.1'})
        self.assertJpeg(r, width=2000, height=2000)

    def test_images_enabled(self):
        r = self.request({'url': self.mockurl("show-image"), 'viewport': '100x100'})
        self.assertPixelColor(r, 30, 30, (0, 0, 0))

    def test_images_disabled(self):
        r = self.request({'url': self.mockurl("show-image"), 'viewport': '100x100', 'images': 0})
        self.assertPixelColor(r, 30, 30, (255, 255, 255))

    def test_very_long_green_page(self):
        r = self.request({'url': self.mockurl("very-long-green-page"),
                          'render_all': 1, 'wait': '0.01', 'viewport': '50x1024', 'quality': '100'})
        self.assertJpeg(r, height=60000)  # hardcoded in the html
        # XXX: JPEG some quality? why 0xFE and not 0xFF?
        self.assertPixelColor(r, 0, 59999, (0x00, 0xFE, 0x77))

    def test_extra_height_doesnt_leave_garbage_when_using_full_render(self):
        r = self.request({'url': self.mockurl('tall'), 'viewport': '100x100',
                          'height': 1000})
        self.assertJpeg(r, height=1000)
        # Ensure that the extra pixels at the bottom are white.
        self.assertBoxColor(r, (0, 100, 100, 1000), (255, 255, 255))

    def test_invalid_scale_method(self):
        for method in ['foo', '1', '']:
            r = self.request({'url': self.mockurl("jsrender"),
                              'scale_method': method})
            self.assertStatusCode(r, 400)

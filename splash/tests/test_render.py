import unittest, requests, json, base64, urllib
from cStringIO import StringIO
from PIL import Image
from splash.tests.utils import TestServers
from splash import defaults

class _BaseRenderTest(unittest.TestCase):

    host = "localhost:%s" % defaults.SPLASH_PORT
    render_format = "html"

    def request(self, query, render_format=None):
        render_format = render_format or self.render_format
        if isinstance(query, dict):
            url= "http://%s/render.%s" % (self.host, render_format)
            return requests.get(url, params=query)
        else:
            url = "http://%s/render.%s?%s" % (self.host, render_format, query)
            return requests.get(url)


class _RenderTest(_BaseRenderTest):

    def test_render_error(self):
        r = self.request("url=http://non-existent-host/")
        self.assertEqual(r.status_code, 502)

    def test_timeout(self):
        r = self.request("url=http://localhost:8998/delay?n=10&timeout=0.5")
        self.assertEqual(r.status_code, 504)

    def test_timeout_out_of_range(self):
        r = self.request("url=http://localhost:8998/delay?n=10&timeout=999")
        self.assertEqual(r.status_code, 400)

    def test_missing_url(self):
        r = self.request("")
        self.assertEqual(r.status_code, 400)
        self.assertTrue("url" in r.text)

    def test_jsalert(self):
        r = self.request("url=http://localhost:8998/jsalert&timeout=3")
        self.assertEqual(r.status_code, 200)

    def test_jsconfirm(self):
        r = self.request("url=http://localhost:8998/jsconfirm&timeout=3")
        self.assertEqual(r.status_code, 200)

    def test_iframes(self):
        r = self.request("url=http://localhost:8998/iframes&timeout=3")
        self.assertEqual(r.status_code, 200)

    def test_wait(self):
        r1 = self.request("url=http://localhost:8998/jsinterval")
        r2 = self.request("url=http://localhost:8998/jsinterval")
        r3 = self.request("url=http://localhost:8998/jsinterval&wait=0.2")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r1.content, r2.content)
        self.assertNotEqual(r1.content, r3.content)


class RenderHtmlTest(_RenderTest):

    render_format = "html"

    def test_ok(self):
        self._test_ok("http://localhost:8998/jsrender")

    def test_ok_https(self):
        self._test_ok("https://localhost:8999/jsrender")

    def _test_ok(self, url):
        r = self.request("url=%s" % url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"].lower(), "text/html; charset=utf-8")
        self.assertTrue("Before" not in r.text)
        self.assertTrue("After" in r.text)

    def test_baseurl(self):
        # first make sure that script.js is served under the right url
        self.assertEqual(404, requests.get("http://localhost:8998/script.js").status_code)
        self.assertEqual(200, requests.get("http://localhost:8998/baseurl/script.js").status_code)

        r = self.request("url=http://localhost:8998/baseurl&baseurl=http://localhost:8998/baseurl/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Before" not in r.text)
        self.assertTrue("After" in r.text)


class RenderPngTest(_RenderTest):

    render_format = "png"

    def test_ok(self):
        self._test_ok("http://localhost:8998/jsrender")

    def test_ok_https(self):
        self._test_ok("https://localhost:8999/jsrender")

    def _test_ok(self, url):
        r = self.request("url=%s" % url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/png")
        img = Image.open(StringIO(r.content))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(img.size, (1024, 768))

    def test_width(self):
        r = self.request("url=http://localhost:8998/jsrender&width=300")
        self.assertEqual(r.headers["content-type"], "image/png")
        img = Image.open(StringIO(r.content))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(img.size[0], 300)

    def test_width_height(self):
        r = self.request("url=http://localhost:8998/jsrender&width=300&height=100")
        self.assertEqual(r.headers["content-type"], "image/png")
        img = Image.open(StringIO(r.content))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(img.size, (300, 100))

    def test_range_checks(self):
        for arg in ('width', 'height', 'vwidth', 'vheight'):
            for val in (-1, 99999):
                r = self.request("url=http://localhost:8998/jsrender&%s=%d" % (arg, val))
                self.assertEqual(r.status_code, 400)


class RenderJsonTest(_RenderTest):
    render_format = 'json'

    def test_jsrender_html(self):
        self.assertSameHtml('http://localhost:8998/jsrender')

    def test_jsrender_https_html(self):
        self.assertSameHtml('https://localhost:8999/jsrender')

    def test_jsalert_html(self):
        self.assertSameHtml('http://localhost:8998/jsalert', {'timeout': 3})

    def test_jsconfirm_html(self):
        self.assertSameHtml("http://localhost:8998/jsconfirm", {'timeout': 3})

    def test_iframes_html(self):
        self.assertSameHtml("http://localhost:8998/iframes", {'timeout': 3})


    def test_jsrender_png(self):
        self.assertSamePng('http://localhost:8998/jsrender')

    def test_jsrender_https_png(self):
        self.assertSamePng('https://localhost:8999/jsrender')

    def test_jsalert_png(self):
        self.assertSamePng('http://localhost:8998/jsalert', {'timeout': 3})

    def test_jsconfirm_png(self):
        self.assertSamePng("http://localhost:8998/jsconfirm", {'timeout': 3})

    def test_iframes_png(self):
        self.assertSamePng("http://localhost:8998/iframes", {'timeout': 3})

    def test_png_size(self):
        self.assertSamePng('http://localhost:8998/jsrender', {'width': 100})
        self.assertSamePng('http://localhost:8998/jsrender', {'width': 100, 'height': 200})
        self.assertSamePng('http://localhost:8998/jsrender',
                           {'width': 100, 'height': 200, 'vwidth': 100, 'vheight': 200})
        self.assertSamePng('http://localhost:8998/jsrender',
                           {'vwidth': 100})


    def test_fields_all(self):
        query = {'url': "https://localhost:8999/iframes",
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

    def test_fields_no_html(self):
        # turn off returning HTML
        query = {'url': "https://localhost:8999/iframes",
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

    def test_fields_no_screenshots(self):
        # turn off screenshots
        query = {'url': "https://localhost:8999/iframes",
                 'html': 1, 'png': 0, 'iframes': 1}
        res = self.request(query).json()
        self.assertFieldsInResponse(res, ["url", "requestedUrl", "childFrames",
                                          "geometry", "title", "html"])
        self.assertFieldsNotInResponse(res, ["png"])

    def test_fields_no_iframes(self):
        query = {'url': "https://localhost:8999/iframes",
                 'html': 1, 'png': 1, 'iframes': 0}
        res = self.request(query).json()
        self.assertFieldsInResponse(res, ["url", "requestedUrl", "geometry",
                                          "title", "html", "png"])
        self.assertFieldsNotInResponse(res, ["childFrames"])

    def test_fields_default(self):
        query = {'url': "https://localhost:8999/iframes"}
        res = self.request(query).json()
        self.assertFieldsInResponse(res, ["url", "requestedUrl", "geometry",
                                          "title"])
        self.assertFieldsNotInResponse(res, ["childFrames", "html", "png"])

    def test_wait(self):
        # override parent's test to make it aware of render.json endpoint
        r1 = self.request({"url": "http://localhost:8998/jsinterval", 'html': 1})
        r2 = self.request({"url": "http://localhost:8998/jsinterval", 'html': 1})
        r3 = self.request({"url": "http://localhost:8998/jsinterval", 'wait': 0.2, 'html': 1})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r3.status_code, 200)

        html1 = r1.json()['html']
        html2 = r2.json()['html']
        html3 = r3.json()['html']
        self.assertEqual(html1, html2)
        self.assertNotEqual(html1, html3)


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
        png1 = base64.decodestring(r1.json()['png'])
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


class IframesRenderTest(_BaseRenderTest):
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
        query = {'url': 'https://localhost:8999/iframes',
                 'iframes': 1, 'html': 1}
        query.update(params or {})
        return self.request(query).json()


class TestTestSetup(unittest.TestCase):

    def test_mockserver_works(self):
        r = requests.get('http://localhost:8998/jsrender')
        self.assertEqual(r.status_code, 200)

    def test_splashserver_works(self):
        r = requests.get('http://localhost:%s/debug' % defaults.SPLASH_PORT)
        self.assertEqual(r.status_code, 200)


ts = TestServers()

def setup():
    ts.__enter__()

def teardown():
    #leaks = requests.get("http://localhost:8050/debug").json()['leaks']
    #assert not leaks, "Leaks detected:\n%s" % leaks
    ts.__exit__(None, None, None)

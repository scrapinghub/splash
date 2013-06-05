import unittest, requests
from cStringIO import StringIO
from PIL import Image
from splash.tests.utils import TestServers

class _RenderTest(unittest.TestCase):

    host = "localhost:8050"
    render_format = "html"

    def request(self, query):
        url = "http://%s/render.%s?%s" % (self.host, self.render_format, query)
        return requests.get(url)

    def test_render_error(self):
        r = self.request("url=http://non-existent-host/")
        self.assertEqual(r.status_code, 502)

    def test_timeout(self):
        r = self.request("url=http://localhost:8998/delay?n=10&timeout=0.5")
        self.assertEqual(r.status_code, 504)

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

class RenderHtmlTest(_RenderTest):

    render_format = "html"

    def test_ok(self):
        r = self.request("url=http://localhost:8998/jsrender")
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
        r = self.request("url=http://localhost:8998/jsrender")
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

ts = TestServers()

def setup():
    ts.__enter__()

def teardown():
    ts.__exit__(None, None, None)

import unittest, requests
from splash2.tests.utils import TestServers

class RenderHtmlTest(unittest.TestCase):

    def test_ok(self):
        with TestServers():
            r = requests.get("http://localhost:8050/render.html?url=http://localhost:8998/jsrender")
            self.assertEqual(r.status_code, 200)
            self.assertTrue("Before" not in r.text)
            self.assertTrue("After" in r.text)

    def test_render_error(self):
        with TestServers():
            r = requests.get("http://localhost:8050/render.html?url=http://non-existent-host/")
            self.assertEqual(r.status_code, 502)

    def test_timeout(self):
        with TestServers():
            r = requests.get("http://localhost:8050/render.html?url=http://localhost:8998/delay?n=10&timeout=0.5")
            self.assertEqual(r.status_code, 504)

    def test_missing_url(self):
        with TestServers():
            r = requests.get("http://localhost:8050/render.html")
            self.assertEqual(r.status_code, 400)
            self.assertTrue("url" in r.text)

    def test_baseurl(self):
        with TestServers():
            # first make sure that script.js is served under the right url
            self.assertEqual(404, requests.get("http://localhost:8998/script.js").status_code)
            self.assertEqual(200, requests.get("http://localhost:8998/baseurl/script.js").status_code)

            r = requests.get("http://localhost:8050/render.html?url=http://localhost:8998/baseurl&baseurl=http://localhost:8998/baseurl/")
            self.assertEqual(r.status_code, 200)
            self.assertTrue("Before" not in r.text)
            self.assertTrue("After" in r.text)

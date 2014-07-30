# -*- coding: utf-8 -*-
from __future__ import absolute_import

from splash import har
from .test_render import BaseRenderTest


class HarRenderTest(BaseRenderTest):
    render_format = 'har'

    def test_jsrender(self):
        url = self.mockurl("jsrender")
        data = self.assertValidHar(url)
        self.assertRequestedUrls(data, [url])

    def test_jsalert(self):
        self.assertValidHar(self.mockurl("jsalert"), timeout=3)

    def test_jsconfirm(self):
        self.assertValidHar(self.mockurl("jsconfirm"), timeout=3)

    def test_iframes(self):
        data = self.assertValidHar(self.mockurl("iframes"), timeout=3)
        self.assertRequestedUrls(data, [
            self.mockurl("iframes"),
            self.mockurl('iframes/1.html'),
            self.mockurl('iframes/2.html'),
            self.mockurl('iframes/3.html'),
            # self.mockurl('iframes/4.html'),  # wait is zero, delayed iframe
            self.mockurl('iframes/5.html'),
            self.mockurl('iframes/6.html'),
            self.mockurl('iframes/script.js'),
            self.mockurl('iframes/script2.js', host="0.0.0.0"),
            self.mockurl('iframes/nested.html'),
        ])

    def test_timeout(self):
        r = self.request({"url": self.mockurl("delay?n=10"), "timeout": 0.5})
        self.assertEqual(r.status_code, 504)

    def test_wait(self):
        self.assertValidHar(self.mockurl("jsinterval"))
        self.assertValidHar(self.mockurl("jsinterval"), wait=0.2)

    def test_meta_redirect_nowait(self):
        data = self.assertValidHar(self.mockurl('meta-redirect0'))
        self.assertRequestedUrls(data, [
            self.mockurl('meta-redirect0'),
        ])

    def test_meta_redirect_wait(self):
        data = self.assertValidHar(self.mockurl('meta-redirect0'), wait=0.1)
        self.assertRequestedUrls(data, [
            self.mockurl('meta-redirect0'),
            self.mockurl('meta-redirect-target/'),
        ])

    def test_meta_redirect_delay_wait(self):
        self.assertValidHar(self.mockurl('meta-redirect1'), wait=0.1)

    def test_meta_redirect_delay_wait_enough(self):
        self.assertValidHar(self.mockurl('meta-redirect1'), wait=0.3)

    def test_meta_redirect_slowload2_wait_more(self):
        self.assertValidHar(self.mockurl('meta-redirect1-slowload2'), wait=0.3)

    def test_redirect_nowait(self):
        self.assertValidHar(self.mockurl('jsredirect'))

    def test_redirect_wait(self):
        self.assertValidHar(self.mockurl('jsredirect'), wait=0.1)

    def test_redirect_onload_nowait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-onload'))
        self.assertRequestedUrls(data, [
            self.mockurl('jsredirect-onload'), # not redirected
        ])

    def test_redirect_onload_wait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-onload'), wait=0.1)
        self.assertRequestedUrls(data, [
            self.mockurl('jsredirect-onload'),
            self.mockurl('jsredirect-target'),
        ])

    def test_redirect_chain_nowait(self):
        self.assertValidHar(self.mockurl('jsredirect-chain'))
        # not redirected

    def test_redirect_chain_wait(self):
        self.assertValidHar(self.mockurl('jsredirect-chain'), wait=0.2)
        # redirected

    def test_redirect_slowimage_nowait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-slowimage'))
        self.assertRequestedUrls(data, [
            self.mockurl('jsredirect-slowimage'),
            self.mockurl('jsredirect-target'),
            self.mockurl('slow.gif?n=2'),
        ])

    def test_redirect_slowimage_wait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-slowimage'), wait=0.1)
        self.assertRequestedUrls(data, [
            self.mockurl('jsredirect-slowimage'),
            self.mockurl('jsredirect-target'),
            self.mockurl('slow.gif?n=2'),
        ])

    def assertValidHarData(self, data, url):
        har.validate(data)
        first_url = data["log"]["entries"][0]["request"]["url"]
        self.assertEqual(first_url, url)

    def assertValidHar(self, url, **params):
        query = {"url": url}
        query.update(params)
        resp = self.request(query)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # from pprint import pprint
        # pprint(data)
        self.assertValidHarData(data, url)
        return data

    def assertRequestedUrls(self, data, urls):
        requested_urls = {e["request"]["url"] for e in data["log"]["entries"]}
        self.assertEqual(requested_urls, set(urls))


class RenderJsonHarTest(HarRenderTest):
    render_format = 'json'

    def assertValidHar(self, url, **params):
        query = {"url": url, "har": 1}
        query.update(params)
        resp = self.request(query)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["har"]
        # from pprint import pprint
        # pprint(data)
        self.assertValidHarData(data, url)
        return data

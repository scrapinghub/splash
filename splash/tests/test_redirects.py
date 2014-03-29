# -*- coding: utf-8 -*-
from __future__ import absolute_import
from splash.tests.test_render import BaseRenderTest
from splash.tests import ts


class HttpRedirectTest(BaseRenderTest):

    def assertHttpRedirectWorks(self, code):
        r = self.request({"url": ts.mockserver.url("http-redirect?code=%s" % code)})
        self.assertEqual(r.status_code, 200)
        self.assertIn("GET request", r.text)
        self.assertIn("{'http_code': ['%s']}" % code, r.text)

    def test_301(self):
        self.assertHttpRedirectWorks(301)

    def test_302(self):
        self.assertHttpRedirectWorks(302)

    def test_303(self):
        self.assertHttpRedirectWorks(303)

    def test_307(self):
        self.assertHttpRedirectWorks(307)


class MetaRedirectTest(BaseRenderTest):

    def assertRedirected(self, resp):
        self.assertEqual(resp.status_code, 200)
        self.assertIn("META REDIRECT TARGET", resp.text)

    def assertNotRedirected(self, resp):
        self.assertEqual(resp.status_code, 200)
        self.assertIn('<meta http-equiv="REFRESH"', resp.text)

    def test_meta_redirect_nowait(self):
        r = self.request({'url': ts.mockserver.url('meta-redirect0')})
        self.assertNotRedirected(r)

    def test_meta_redirect_wait(self):
        r = self.request({
            'url': ts.mockserver.url('meta-redirect0'),
            'wait': 0.1,
        })
        self.assertRedirected(r)

    def test_meta_redirect_delay_wait(self):
        r = self.request({
            'url': ts.mockserver.url('meta-redirect1'),
            'wait': 0.1,
        })
        self.assertNotRedirected(r)

    def test_meta_redirect_delay_wait_enough(self):
        r = self.request({
            'url': ts.mockserver.url('meta-redirect1'),
            'wait': 0.3,
        })
        self.assertRedirected(r)

    def test_meta_redirect_slowload(self):
        r = self.request({'url': ts.mockserver.url('meta-redirect-slowload')})
        self.assertNotRedirected(r)

    def test_meta_redirect_slowload_wait(self):
        r = self.request({
            'url': ts.mockserver.url('meta-redirect-slowload'),
            'wait': 0.1,
        })
        self.assertRedirected(r)

    def test_meta_redirect_slowload_wait_more(self):
        r = self.request({
            'url': ts.mockserver.url('meta-redirect-slowload'),
            'wait': 0.3,
        })
        self.assertRedirected(r)

    def test_meta_redirect_slowload2(self):
        r = self.request({'url': ts.mockserver.url('meta-redirect-slowload2')})
        self.assertNotRedirected(r)

    def test_meta_redirect_slowload2_wait(self):
        r = self.request({
            'url': ts.mockserver.url('meta-redirect-slowload2'),
            'wait': 0.1,
        })
        self.assertRedirected(r)

    def test_meta_redirect_slowload2_wait_more(self):
        r = self.request({
            'url': ts.mockserver.url('meta-redirect-slowload2'),
            'wait': 0.3,
        })
        self.assertRedirected(r)


class JsRedirectTest(BaseRenderTest):
    def assertRedirected(self, resp):
        self.assertEqual(resp.status_code, 200)
        self.assertIn("JS REDIRECT TARGET", resp.text)

    def assertNotRedirected(self, resp):
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("JS REDIRECT TARGET", resp.text)
        self.assertIn("Redirecting", resp.text)

    def test_redirect_nowait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect')})
        self.assertNotRedirected(r)

    def test_redirect_wait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect'), 'wait': 0.1})
        self.assertRedirected(r)

    def test_redirect_onload_nowait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect-onload')})
        self.assertNotRedirected(r)

    def test_redirect_onload_wait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect-onload'), 'wait': 0.1})
        self.assertRedirected(r)

    def test_redirect_timer_nowait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect-timer')})
        self.assertNotRedirected(r)

    def test_redirect_timer_wait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect-timer'), 'wait': 0.05})
        self.assertNotRedirected(r)

    def test_redirect_timer_wait_enough(self):
        r = self.request({'url': ts.mockserver.url('jsredirect-timer'), 'wait': 0.2})
        self.assertRedirected(r)

    def test_redirect_chain_nowait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect-chain')})
        self.assertNotRedirected(r)

    def test_redirect_chain_wait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect-chain'), 'wait': 0.2})
        self.assertRedirected(r)

    def test_redirect_slowimage_nowait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect-slowimage')})
        self.assertNotRedirected(r)

    def test_redirect_slowimage_wait(self):
        r = self.request({'url': ts.mockserver.url('jsredirect-slowimage'), 'wait': 0.1})
        self.assertRedirected(r)

    def test_redirect_slowimage_nowait_baseurl(self):
        r = self.request({
            'url': ts.mockserver.url('jsredirect-slowimage'),
            'baseurl': ts.mockserver.url('/'),
        })
        self.assertNotRedirected(r)

    def test_redirect_slowimage_wait_baseurl(self):
        r = self.request({
            'url': ts.mockserver.url('jsredirect-slowimage'),
            'baseurl': ts.mockserver.url('/'),
            'wait': 0.1
        })
        self.assertRedirected(r)

    # TODO: support for jsredirect-infinite

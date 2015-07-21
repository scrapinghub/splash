# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest
import six
from splash.tests.test_render import BaseRenderTest
from splash.tests.utils import NON_EXISTING_RESOLVABLE


class HttpRedirectTest(BaseRenderTest):

    def assertRedirectedResponse(self, resp, code):
        self.assertStatusCode(resp, 200)
        self.assertIn("GET request", resp.text)
        if six.PY3:
            self.assertIn("{b'http_code': [b'%s']}" % code, resp.text)
        else:
            self.assertIn("{'http_code': ['%s']}" % code, resp.text)

    def assertHttpRedirectWorks(self, code):
        resp = self.request({"url": self.mockurl("http-redirect?code=%s" % code)})
        self.assertRedirectedResponse(resp, code)

    def assertBaseurlHttpRedirectWorks(self, code):
        url = self.mockurl("http-redirect?code=%s" % code)
        resp = self.request({"url": url, "baseurl": url})
        self.assertRedirectedResponse(resp, code)

    def test_301(self):
        self.assertHttpRedirectWorks(301)

    def test_302(self):
        self.assertHttpRedirectWorks(302)

    def test_303(self):
        self.assertHttpRedirectWorks(303)

    def test_307(self):
        self.assertHttpRedirectWorks(307)

    def test_301_baseurl(self):
        self.assertBaseurlHttpRedirectWorks(301)

    def test_302_baseurl(self):
        self.assertBaseurlHttpRedirectWorks(302)

    def test_303_baseurl(self):
        self.assertBaseurlHttpRedirectWorks(303)

    def test_307_baseurl(self):
        self.assertBaseurlHttpRedirectWorks(307)


class MetaRedirectTest(BaseRenderTest):

    def assertRedirected(self, resp):
        self.assertStatusCode(resp, 200)
        self.assertIn("META REDIRECT TARGET", resp.text)

    def assertNotRedirected(self, resp):
        self.assertStatusCode(resp, 200)
        self.assertIn('<meta http-equiv="REFRESH"', resp.text)

    def test_meta_redirect_nowait(self):
        r = self.request({'url': self.mockurl('meta-redirect0')})
        self.assertNotRedirected(r)

    def test_meta_redirect_wait(self):
        r = self.request({'url': self.mockurl('meta-redirect0'), 'wait': '0.1'})
        self.assertRedirected(r)

    def test_meta_redirect_delay_wait(self):
        r = self.request({'url': self.mockurl('meta-redirect1'), 'wait': '0.1'})
        self.assertNotRedirected(r)

    def test_meta_redirect_delay_wait_enough(self):
        r = self.request({'url': self.mockurl('meta-redirect1'), 'wait': '0.3'})
        self.assertRedirected(r)

    def test_meta_redirect_slowload(self):
        r = self.request({'url': self.mockurl('meta-redirect-slowload')})
        self.assertNotRedirected(r)

    def test_meta_redirect_slowload_wait(self):
        r = self.request({
            'url': self.mockurl('meta-redirect-slowload'),
            'wait': '0.1',
        })
        self.assertRedirected(r)

    def test_meta_redirect_slowload_wait_more(self):
        r = self.request({
            'url': self.mockurl('meta-redirect-slowload'),
            'wait': '0.3',
        })
        self.assertRedirected(r)

    def test_meta_redirect_slowload2(self):
        r = self.request({'url': self.mockurl('meta-redirect-slowload2')})
        self.assertNotRedirected(r)

    def test_meta_redirect_slowload2_wait(self):
        r = self.request({
            'url': self.mockurl('meta-redirect-slowload2'),
            'wait': '0.1',
        })
        self.assertRedirected(r)

    def test_meta_redirect_slowload2_wait_more(self):
        r = self.request({
            'url': self.mockurl('meta-redirect-slowload2'),
            'wait': '0.3',
        })
        self.assertRedirected(r)


class JsRedirectTest(BaseRenderTest):
    def assertRedirected(self, resp):
        self.assertStatusCode(resp, 200)
        self.assertIn("JS REDIRECT TARGET", resp.text)

    def assertNotRedirected(self, resp):
        self.assertStatusCode(resp, 200)
        self.assertNotIn("JS REDIRECT TARGET", resp.text)
        self.assertIn("Redirecting", resp.text)

    def test_redirect_nowait(self):
        r = self.request({'url': self.mockurl('jsredirect')})
        self.assertNotRedirected(r)

    def test_redirect_wait(self):
        r = self.request({'url': self.mockurl('jsredirect'), 'wait': '0.1'})
        self.assertRedirected(r)

    def test_redirect_onload_nowait(self):
        r = self.request({'url': self.mockurl('jsredirect-onload')})
        self.assertNotRedirected(r)

    def test_redirect_onload_wait(self):
        r = self.request({'url': self.mockurl('jsredirect-onload'), 'wait': '0.1'})
        self.assertRedirected(r)

    def test_redirect_timer_nowait(self):
        r = self.request({'url': self.mockurl('jsredirect-timer')})
        self.assertNotRedirected(r)

    def test_redirect_timer_wait(self):
        # jsredirect-timer redirects after 0.1ms
        r = self.request({'url': self.mockurl('jsredirect-timer'), 'wait': '0.05'})
        self.assertNotRedirected(r)

    def test_redirect_timer_wait_enough(self):
        # jsredirect-timer redirects after 0.1s
        r = self.request({'url': self.mockurl('jsredirect-timer'), 'wait': '0.2'})
        self.assertRedirected(r)

    def test_redirect_chain_nowait(self):
        r = self.request({'url': self.mockurl('jsredirect-chain')})
        self.assertNotRedirected(r)

    def test_redirect_chain_wait(self):
        r = self.request({'url': self.mockurl('jsredirect-chain'), 'wait': '0.2'})
        self.assertRedirected(r)

    def test_redirect_slowimage_nowait(self):
        r = self.request({'url': self.mockurl('jsredirect-slowimage')})
        self.assertRedirected(r)

    def test_redirect_slowimage_wait(self):
        r = self.request({'url': self.mockurl('jsredirect-slowimage'), 'wait': '0.1'})
        self.assertRedirected(r)

    def test_redirect_slowimage_nowait_baseurl(self):
        r = self.request({
            'url': self.mockurl('jsredirect-slowimage'),
            'baseurl': self.mockurl('/'),
        })
        self.assertRedirected(r)

    def test_redirect_slowimage_wait_baseurl(self):
        r = self.request({
            'url': self.mockurl('jsredirect-slowimage'),
            'baseurl': self.mockurl('/'),
            'wait': '0.1'
        })
        self.assertRedirected(r)

    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_redirect_to_non_existing(self):
        r = self.request({
            "url": self.mockurl("jsredirect-non-existing"),
            "wait": '2.',
        })
        self.assertStatusCode(r, 502)

    # TODO: support for jsredirect-infinite

# -*- coding: utf-8 -*-
from __future__ import absolute_import
import base64
import requests
import warnings
import unittest

import pytest

from splash.har import schema
from splash.har.utils import entries2pages
from splash.qtutils import qt_551_plus
from splash.tests import test_redirects
from splash.tests.utils import NON_EXISTING_RESOLVABLE
from .test_render import BaseRenderTest


class BaseHarRenderTest(BaseRenderTest):
    endpoint = 'render.har'

    try:
        schema.get_validator()
        VALIDATION_SUPPORTED = True
    except Exception as e:
        warnings.warn("jsonschema validation is not supported and will be skipped. "
                      "Please install jsonschema >= 2.0 or jsonschema >= 1.0 + isodate. "
                      "Exception: %r" % e)
        VALIDATION_SUPPORTED = False

    def assertValidHarData(self, data, url):
        if self.VALIDATION_SUPPORTED:
            schema.validate(data)

        first_url = data["log"]["entries"][0]["request"]["url"]
        self.assertEqual(first_url, url)

    def assertValidHar(self, url, **params):
        query = {"url": url}
        query.update(params)
        resp = self.request(query)
        self.assertStatusCode(resp, 200)
        data = resp.json()
        # from pprint import pprint
        # pprint(data)
        self.assertValidHarData(data, url)
        self.assertValidTimings(data)
        return data

    def assertRequestedUrls(self, data, correct_urls):
        requested_urls = {e["request"]["url"] for e in data["log"]["entries"]}
        self.assertEqual(requested_urls, set(correct_urls))

    def assertRequestedUrlsStatuses(self, data, correct_urls_statuses):
        urls_statuses = {
            (e["request"]["url"], e["response"]["status"])
            for e in data["log"]["entries"]
        }
        self.assertEqual(urls_statuses, set(correct_urls_statuses))

    def assertValidTimings(self, data):
        page0 = data['log']['pages'][0]
        self.assertIn("_onStarted", page0["pageTimings"])


class HarRenderTest(BaseHarRenderTest):
    """ Tests for HAR data in render.har endpoint """

    def test_jsrender(self):
        url = self.mockurl("jsrender")
        data = self.assertValidHar(url)
        self.assertRequestedUrlsStatuses(data, [(url, 200)])

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

    def test_iframes_wait(self):
        data = self.assertValidHar(self.mockurl("iframes"), timeout=3, wait=0.5)
        self.assertRequestedUrls(data, [
            self.mockurl("iframes"),
            self.mockurl('iframes/1.html'),
            self.mockurl('iframes/2.html'),
            self.mockurl('iframes/3.html'),
            self.mockurl('iframes/4.html'),  # wait is not zero, delayed iframe
            self.mockurl('iframes/5.html'),
            self.mockurl('iframes/6.html'),
            self.mockurl('iframes/script.js'),
            self.mockurl('iframes/script2.js', host="0.0.0.0"),
            self.mockurl('iframes/nested.html'),
        ])

    def test_timeout(self):
        r = self.request({"url": self.mockurl("delay?n=10"), "timeout": 0.5})
        self.assertStatusCode(r, 504)

    def test_wait(self):
        self.assertValidHar(self.mockurl("jsinterval"))
        self.assertValidHar(self.mockurl("jsinterval"), wait=0.2)

    def test_meta_redirect_nowait(self):
        data = self.assertValidHar(self.mockurl('meta-redirect0'))
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('meta-redirect0'), 200),
        ])

    def test_meta_redirect_wait(self):
        data = self.assertValidHar(self.mockurl('meta-redirect0'), wait=0.1)
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('meta-redirect0'), 200),
            (self.mockurl('meta-redirect-target/'), 200),
        ])

    def test_meta_redirect_delay_wait(self):
        data = self.assertValidHar(self.mockurl('meta-redirect1'), wait=0.1)
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('meta-redirect1'), 200),
        ])

    def test_meta_redirect_delay_wait_enough(self):
        data = self.assertValidHar(self.mockurl('meta-redirect1'), wait=0.3)
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('meta-redirect1'), 200),
            (self.mockurl('meta-redirect-target/'), 200),
        ])

    def test_meta_redirect_slowload2_wait_more(self):
        data = self.assertValidHar(self.mockurl('meta-redirect-slowload2'), wait=0.3)
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('meta-redirect-slowload2'), 200),
            (self.mockurl('slow.gif?n=2'), 200),
            (self.mockurl('meta-redirect-target/'), 200),
        ])

    def test_redirect_nowait(self):
        data = self.assertValidHar(self.mockurl('jsredirect'))
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('jsredirect'), 200),
        ])

    def test_redirect_wait(self):
        data = self.assertValidHar(self.mockurl('jsredirect'), wait=0.1)
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('jsredirect'), 200),
            (self.mockurl('jsredirect-target'), 200),
        ])

    def test_redirect_onload_nowait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-onload'))
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('jsredirect-onload'), 200)  # not redirected
        ])

    def test_redirect_onload_wait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-onload'), wait=0.1)
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('jsredirect-onload'), 200),
            (self.mockurl('jsredirect-target'), 200),
        ])

    def test_redirect_chain_nowait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-chain'))
        # not redirected
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('jsredirect-chain'), 200),
        ])

    def test_response_body(self):
        url = self.mockurl('show-image')
        data = self.assertValidHar(url)
        for entry in data['log']['entries']:
            assert 'text' not in entry['response']['content']

        data = self.assertValidHar(url, response_body=1)
        entries = data['log']['entries']
        assert len(entries) == 2
        for entry in entries:
            assert 'text' in entry['response']['content']

        img_gif = requests.get(self.mockurl('slow.gif?n=0')).content
        b64_data = entries[1]['response']['content']['text']
        assert base64.b64decode(b64_data) == img_gif

    def test_redirect_chain_wait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-chain'), wait=0.2)
        # redirected
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('jsredirect-chain'), 200),
            (self.mockurl('jsredirect'), 200),
            (self.mockurl('jsredirect-target'), 200),
        ])

    @pytest.mark.xfail(reason=qt_551_plus())  # why is it failing?
    def test_redirect_slowimage_nowait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-slowimage'))
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('jsredirect-slowimage'), 200),
            (self.mockurl('jsredirect-target'), 200),
            (self.mockurl('slow.gif?n=2'), 0),
        ])

        pages = entries2pages(data["log"]["entries"])
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(pages[0]), 2)  # jsredirect-slowimage and slow.gif?n=2
        self.assertEqual(len(pages[1]), 1)  # jsredirect-target
        self.assertEqual(pages[0][1]["response"]["statusText"], "cancelled")

    @pytest.mark.xfail(reason=qt_551_plus())  # why is it failing?
    def test_redirect_slowimage_wait(self):
        data = self.assertValidHar(self.mockurl('jsredirect-slowimage'), wait=0.1)
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('jsredirect-slowimage'), 200),
            (self.mockurl('jsredirect-target'), 200),
            (self.mockurl('slow.gif?n=2'), 0),
        ])

    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_bad_related(self):
        data = self.assertValidHar(self.mockurl("bad-related"))
        self.assertRequestedUrlsStatuses(data, [
            (self.mockurl('bad-related'), 200),
            ('http://non-existing/', 0),
        ])
        pages = entries2pages(data["log"]["entries"])
        self.assertEqual(len(pages), 1)
        self.assertEqual(len(pages[0]), 2)
        self.assertEqual(pages[0][1]["response"]["statusText"], "invalid_hostname")

    def test_cookies(self):
        data = self.assertValidHar(self.mockurl("set-cookie?key=foo&value=bar"))
        entry = data['log']['entries'][0]
        self.assertEqual(entry['response']['cookies'], [
            {
                'path': '',
                'name': 'foo',
                'httpOnly': False,
                'domain': '',
                'value': 'bar',
                'secure': False
             }
        ])

    def test_invalid_status_code_message(self):
        data = self.assertValidHar(self.mockurl("bad-status-code-message"),
                                   timeout=3)
        pages = data['log']['entries']
        self.assertEqual(len(pages), 1)
        resp = pages[0]['response']
        self.assertEqual(resp['status'], 200)
        self.assertEqual(resp['statusText'],
                         u'успех'.encode('cp1251').decode('latin1'))


class HarHttpRedirectTest(test_redirects.HttpRedirectTest, BaseHarRenderTest):

    def assertHarRedirectedResponse(self, resp, code, url):
        self.assertStatusCode(resp, 200)
        data = resp.json()
        self.assertValidHarData(data, url)
        self.assertRequestedUrlsStatuses(data, [
            (url, code),
            (self.mockurl('getrequest?http_code=%s' % code), 200)
        ])
        redir_url = data["log"]["entries"][0]["response"]["redirectURL"]
        self.assertEqual(redir_url, "/getrequest?http_code=%s" % code)

    def assertBaseurlHttpRedirectWorks(self, code):
        url = self.mockurl("http-redirect?code=%s" % code)
        resp = self.request({"url": url, "baseurl": url})
        self.assertHarRedirectedResponse(resp, code, url)

    def assertHttpRedirectWorks(self, code):
        url = self.mockurl("http-redirect?code=%s" % code)
        resp = self.request({"url": url})
        self.assertHarRedirectedResponse(resp, code, url)


class RenderJsonHarTest(HarRenderTest):
    """ Tests for HAR data in render.json endpoint """

    endpoint = 'render.json'

    def assertValidHar(self, url, **params):
        query = {"url": url, "har": 1}
        query.update(params)
        resp = self.request(query)
        self.assertStatusCode(resp, 200)
        data = resp.json()["har"]
        # from pprint import pprint
        # pprint(data)
        self.assertValidHarData(data, url)
        return data

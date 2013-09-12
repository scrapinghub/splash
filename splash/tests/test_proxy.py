# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest
from splash.proxy import BlackWhiteSplashProxyFactory, ProfilesSplashProxyFactory
from .test_render import _BaseRenderTest

class BlackWhiteProxyFactoryTest(unittest.TestCase):

    def _factory(self, **kwargs):
        params = {
            "proxy_list": [("proxy.crawlera.com", 8010, "username", "password")],
            "whitelist": [
                r".*scrapinghub\.com.*",
            ],
            "blacklist": [
                r".*\.js",
                r".*\.css",
            ]
        }
        params.update(kwargs)
        return BlackWhiteSplashProxyFactory(**params)

    def test_noproxy(self):
        f = BlackWhiteSplashProxyFactory()
        self.assertFalse(f.shouldUseProxyList('http', 'crawlera.com'))

    def test_whitelist(self):
        self.assertUsesCustom('http://www.scrapinghub.com')
        self.assertUsesDefault('http://www.google-analytics.com/ga.js')
        self.assertUsesDefault('http://crawlera.com')

    def test_blacklist(self):
        self.assertUsesDefault('http://www.scrapinghub.com/static/styles/screen.css')

    def test_no_whitelist(self):
        self.assertUsesCustom('http://crawlera.com', whitelist=[])
        self.assertUsesDefault('http://www.google-analytics.com/ga.js', whitelist=[])


    def assertUsesDefault(self, url, protocol='http', **kwargs):
        f = self._factory(**kwargs)
        self.assertFalse(f.shouldUseProxyList(protocol, url))

    def assertUsesCustom(self, url, protocol='http', **kwargs):
        f = self._factory(**kwargs)
        self.assertTrue(f.shouldUseProxyList(protocol, url))


class HtmlProxyRenderTest(_BaseRenderTest):

    def test_proxy_works(self):
        r1 = self.request({'url': 'http://localhost:8998/jsrender'})
        self.assertNotProxied(r1.text)

        r2 = self.request({'url': 'http://localhost:8998/jsrender', 'proxy': 'test'})
        self.assertProxied(r2.text)

    def test_blacklist(self):
        params = {'url': 'http://localhost:8998/iframes',
                  'proxy': 'test', 'html': 1, 'iframes': 1}
        r = self.request(params, render_format='json')
        data = r.json()

        # only 1.html is blacklisted in test.ini
        self.assertProxied(data['html'])
        assert any('1.html' in f['requestedUrl'] for f in data['childFrames'])

        for frame in data['childFrames']:
            if '1.html' in frame['requestedUrl']:
                self.assertNotProxied(frame['html'])
            else:
                self.assertProxied(frame['html'])

    def test_insecure(self):
        r = self.request({'url': 'http://localhost:8998/jsrender',
                          'proxy': '../this-is-not-a-proxy-profile'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.text.strip(), ProfilesSplashProxyFactory.NO_PROXY_PROFILE_MSG)


    def test_nonexisting(self):
        r = self.request({'url': 'http://localhost:8998/jsrender',
                          'proxy': 'nonexisting'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.text.strip(), ProfilesSplashProxyFactory.NO_PROXY_PROFILE_MSG)

    def test_no_proxy_settings(self):
        r = self.request({'url': 'http://localhost:8998/jsrender',
                          'proxy': 'no-proxy-settings'})
        self.assertEqual(r.status_code, 400)


    def assertProxied(self, html):
        assert 'PROXY_USED' in html

    def assertNotProxied(self, html):
        assert 'PROXY_USED' not in html

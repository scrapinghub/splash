# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest
from splash.proxy import SplashQNetworkProxyFactory

class ProxyFactoryTest(unittest.TestCase):

    def _factory(self, **kwargs):
        params = {
            "proxy_list": [("proxy.crawlera.com", 8010, "username", "password")],
            "whitelist": [
                r".*scrapinghub\.com.*"
            ],
            "blacklist": [
                r".*\.js",
                r".*\.css",
            ]
        }
        params.update(kwargs)
        return SplashQNetworkProxyFactory(**params)

    def test_noproxy(self):
        f = SplashQNetworkProxyFactory()
        self.assertTrue(f.shouldUseDefault('http', 'crawlera.com'))

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
        self.assertTrue(f.shouldUseDefault(protocol, url))

    def assertUsesCustom(self, url, protocol='http', **kwargs):
        f = self._factory(**kwargs)
        self.assertFalse(f.shouldUseDefault(protocol, url))

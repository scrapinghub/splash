# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil
import unittest
import requests
from splash.proxy import _BlackWhiteSplashProxyFactory, ProfilesSplashProxyFactory
from splash.tests.test_render import BaseRenderTest
from splash.tests.utils import TestServers

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
        return _BlackWhiteSplashProxyFactory(**params)

    def test_noproxy(self):
        f = _BlackWhiteSplashProxyFactory()
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


class BaseHtmlProxyTest(BaseRenderTest):
    use_gzip = False  # our simple testing proxy dosn't work with gzip

    def assertProxied(self, html):
        assert 'PROXY_USED' in html

    def assertNotProxied(self, html):
        assert 'PROXY_USED' not in html


class HtmlProxyRenderTest(BaseHtmlProxyTest):

    def test_proxy_works(self):
        r1 = self.request({'url': self.mockurl('jsrender')})
        self.assertNotProxied(r1.text)

        r2 = self.request({'url': self.mockurl('jsrender'), 'proxy': 'test'})
        self.assertProxied(r2.text)

    def test_blacklist(self):
        params = {'url': self.mockurl('iframes'),
                  'proxy': 'test', 'html': 1, 'iframes': 1}
        r = self.request(params, endpoint='render.json')
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
        r = self.request({'url': self.mockurl('jsrender'),
                          'proxy': '../this-is-not-a-proxy-profile'})
        self.assertStatusCode(r, 400)
        self.assertEqual(r.text.strip(), ProfilesSplashProxyFactory.NO_PROXY_PROFILE_MSG)


    def test_nonexisting(self):
        r = self.request({'url': self.mockurl('jsrender'),
                          'proxy': 'nonexisting'})
        self.assertStatusCode(r, 400)
        self.assertEqual(r.text.strip(), ProfilesSplashProxyFactory.NO_PROXY_PROFILE_MSG)

    def test_no_proxy_settings(self):
        r = self.request({'url': self.mockurl('jsrender'),
                          'proxy': 'no-proxy-settings'})
        self.assertStatusCode(r, 400)


class HtmlProxyDefaultProfileTest(BaseHtmlProxyTest):

    def ts2_request(self, ts2, query, endpoint='render.html'):
        url = "http://localhost:%s/%s" % (ts2.splashserver.portnum, endpoint)
        return requests.get(url, params=query)

    def create_default_ini(self, ts2):
        src = os.path.join(ts2.proxy_profiles_path, 'test.ini')
        dst = os.path.join(ts2.proxy_profiles_path, 'default.ini')
        shutil.copyfile(src, dst)

    def remove_default_ini(self, ts2):
        dst = os.path.join(ts2.proxy_profiles_path, 'default.ini')
        os.unlink(dst)

    def test_ts_setup(self):
        with TestServers() as ts2:
            r1 = self.ts2_request(ts2, {'url': ts2.mockserver.url('jsrender', gzip=False)})
            self.assertNotProxied(r1.text)

            r2 = self.ts2_request(ts2, {
                'url': ts2.mockserver.url('jsrender', gzip=False),
                'proxy': 'test',
            })
            self.assertProxied(r2.text)

    def test_default_profile_works(self):
        with TestServers() as ts2:
            self.create_default_ini(ts2)
            try:
                # default.ini present, proxy is used by default
                r1 = self.ts2_request(ts2, {'url': ts2.mockserver.url('jsrender', gzip=False)})
                self.assertProxied(r1.text)

                # another proxy
                r2 = self.ts2_request(ts2, {
                    'url': ts2.mockserver.url('jsrender', gzip=False),
                    'proxy': 'test',
                })
                self.assertProxied(r2.text)

                # invalid proxy profile
                r3 = self.ts2_request(ts2, {
                    'url': ts2.mockserver.url('jsrender', gzip=False),
                    'proxy': 'nonexisting',
                })
                self.assertStatusCode(r3, 400)

                # 'none' disables default.ini
                r4 = self.ts2_request(ts2, {
                    'url': ts2.mockserver.url('jsrender', gzip=False),
                    'proxy': 'none',
                })
                self.assertNotProxied(r4.text)

                # empty 'proxy' argument disables default.ini
                r5 = self.ts2_request(ts2, {
                    'url': ts2.mockserver.url('jsrender', gzip=False),
                    'proxy': '',
                })
                self.assertNotProxied(r5.text)

            finally:
                self.remove_default_ini(ts2)

# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil
import unittest
import requests
from splash.proxy import (
        _BlackWhiteSplashProxyFactory,
        ProfilesSplashProxyFactory,
        DirectSplashProxyFactory)
from splash.qtutils import PROXY_TYPES
from splash.render_options import BadOption
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
        self.assertFalse(f.should_use_proxy_list('http', 'crawlera.com'))

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
        self.assertFalse(f.should_use_proxy_list(protocol, url))

    def assertUsesCustom(self, url, protocol='http', **kwargs):
        f = self._factory(**kwargs)
        self.assertTrue(f.should_use_proxy_list(protocol, url))


class DirectSplashProxyFactoryTest(unittest.TestCase):
    def test_parse(self):
        factory = DirectSplashProxyFactory('http://pepe:hunter2@proxy.com:1234')
        self.assertEquals(factory.proxy.port(), 1234)
        self.assertEquals(factory.proxy.user(), 'pepe')
        self.assertEquals(factory.proxy.password(), 'hunter2')
        self.assertEquals(factory.proxy.hostName(), 'proxy.com')
        self.assertEquals(factory.proxy.type(), PROXY_TYPES['HTTP'])

    def test_default_port(self):
        factory = DirectSplashProxyFactory('http://proxy.com')
        self.assertEquals(factory.proxy.port(), 1080)

    def test_socks5(self):
        factory = DirectSplashProxyFactory('socks5://proxy.com')
        self.assertEquals(factory.proxy.type(), PROXY_TYPES['SOCKS5'])

    def test_invalid(self):
        with self.assertRaises(BadOption):
            DirectSplashProxyFactory('This is not a valid URL')
        with self.assertRaises(BadOption):
            DirectSplashProxyFactory('ftp://proxy.com')
        with self.assertRaises(BadOption):
            DirectSplashProxyFactory('relative_url')


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
        data = self.assertJsonError(r, 400, 'BadOption')
        self.assertEqual(
            data['info']['description'],
            ProfilesSplashProxyFactory.NO_PROXY_PROFILE_MSG
        )

    def test_nonexisting(self):
        r = self.request({'url': self.mockurl('jsrender'),
                          'proxy': 'nonexisting'})
        data = self.assertJsonError(r, 400, 'BadOption')
        self.assertEqual(
            data['info']['description'],
            ProfilesSplashProxyFactory.NO_PROXY_PROFILE_MSG
        )

    def test_no_proxy_settings(self):
        r = self.request({'url': self.mockurl('jsrender'),
                          'proxy': 'no-proxy-settings'})
        self.assertJsonError(r, 400, 'BadOption')


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


class ProxyInParameterTest(BaseHtmlProxyTest):
    def test_proxy_works(self):
        r1 = self.request({'url': self.mockurl('jsrender')})
        self.assertNotProxied(r1.text)

        r2 = self.request({
            'url': self.mockurl('jsrender'),
            'proxy': 'http://0.0.0.0:%s' % self.ts.mock_proxy_port
        })
        self.assertProxied(r2.text)

    def test_proxy_post(self):
        r1 = self.request({'url': self.mockurl('jspost'), 'wait': '0.1'})
        self.assertNotProxied(r1.text)
        self.assertIn('application/x-www-form-urlencoded', r1.text)

        r2 = self.request({
            'url': self.mockurl('jspost'),
            'wait': '0.1',
            'proxy': 'http://0.0.0.0:%s' % self.ts.mock_proxy_port
        })
        self.assertProxied(r2.text)
        self.assertIn('application/x-www-form-urlencoded', r2.text)

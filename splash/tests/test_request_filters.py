# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil

import requests
import pytest

from splash.tests.utils import TestServers, SplashServer
from splash.tests.test_render import BaseRenderTest


class BaseFiltersTest(BaseRenderTest):
    def assertFiltersWork(self, resp, noscript, noscript2):
        """
        Check that filters work. There are two testing filters
        (see splash/tests/filters), "noscript" that filters script.js,
        and "noscript2" that filters script2.js.

        ``resp`` must be a response returned by a request to 'iframes'
        endpoint of mock server. ``noscript`` and ``noscript2`` are boolean
        variables.
        """
        if noscript:
            self.assertNotIn('SAME_DOMAIN', resp.text)
        else:
            self.assertIn('SAME_DOMAIN', resp.text)

        if noscript2:
            self.assertNotIn('OTHER_DOMAIN', resp.text)
        else:
            self.assertIn('OTHER_DOMAIN', resp.text)

    def params(self, **kwargs):
        kwargs.setdefault('url', self.mockurl('iframes'))
        return kwargs


class FiltersTestHTML(BaseFiltersTest):

    def test_filtering_works(self):
        r = self.request(self.params())
        self.assertFiltersWork(r, noscript=False, noscript2=False)

        r = self.request(self.params(filters='noscript'))
        self.assertFiltersWork(r, noscript=True, noscript2=False)

        r = self.request(self.params(filters='noscript2'))
        self.assertFiltersWork(r, noscript=False, noscript2=True)

    def test_multiple_filters(self):
        r = self.request(self.params(filters='noscript,noscript2'))
        self.assertFiltersWork(r, noscript=True, noscript2=True)

    def test_invalid_filters(self):
        r = self.request(self.params(filters='foo,noscript2'))
        self.assertStatusCode(r, 400)
        self.assertIn('foo', r.text)

    def test_dont_filter_main_request_with_domain_option(self):
        r = self.request({
            'url': self.mockurl('iframes/script.js'),
            'filters': 'noscript'
        })
        self.assertStatusCode(r, 200)
        self.assertIn('document.write', r.text)

    @pytest.mark.xfail(reason="See https://github.com/scrapinghub/splash/issues/399")
    def test_dont_filter_main_request_without_domain_option(self):
        r = self.request({
            'url': self.mockurl('iframes/script2.js'),
            'filters': 'noscript2'
        })
        self.assertStatusCode(r, 200)
        self.assertIn('document.write', r.text)


class DefaultFiltersTest(BaseFiltersTest):
    def ts_request(self, ts2, query=None, endpoint='render.html'):
        url = "http://localhost:%s/%s" % (ts2.splashserver.portnum, endpoint)
        return requests.get(url, params=self.params(**(query or {})))

    def create_default_txt(self, ts2, copy_from):
        src = os.path.join(ts2.filters_path, copy_from)
        dst = os.path.join(ts2.filters_path, 'default.txt')
        shutil.copyfile(src, dst)

    def remove_default_ini(self, ts2):
        dst = os.path.join(ts2.filters_path, 'default.txt')
        os.unlink(dst)

    def test_testing_setup(self):
        with TestServers() as ts2:
            # no filters, no default.txt
            r = self.ts_request(ts2)
            self.assertFiltersWork(r, noscript=False, noscript2=False)

            # default.txt does not exist yet
            r = self.ts_request(ts2, {'filters': 'default'})
            self.assertStatusCode(r, 400)
            self.assertIn('default', r.text)

    def test_default_works(self):

        ts2 = TestServers()

        # create default.txt. It is the same as 'noscript.txt'.
        self.create_default_txt(ts2, copy_from='noscript.txt')

        with ts2:
            try:
                r = self.ts_request(ts2, {'filters': 'default'})
                self.assertFiltersWork(r, noscript=True, noscript2=False)

                r = self.ts_request(ts2)
                self.assertFiltersWork(r, noscript=True, noscript2=False)

                r = self.ts_request(ts2, {'filters': 'noscript'})
                self.assertFiltersWork(r, noscript=True, noscript2=False)

                r = self.ts_request(ts2, {'filters': 'noscript2'})
                self.assertFiltersWork(r, noscript=False, noscript2=True)

                r = self.ts_request(ts2, {'filters': 'noscript2,default'})
                self.assertFiltersWork(r, noscript=True, noscript2=True)

                r = self.ts_request(ts2, {'filters': 'noscript,default'})
                self.assertFiltersWork(r, noscript=True, noscript2=False)

                r = self.ts_request(ts2, {'filters': 'none'})
                self.assertFiltersWork(r, noscript=False, noscript2=False)

            finally:
                self.remove_default_ini(ts2)


class AllowedSchemesTest(BaseRenderTest):

    FILE_PATH = os.path.join(
        os.path.dirname(__file__), 'filters', 'noscript.txt'
    )
    FILE_URL = 'file://' + FILE_PATH

    def test_file_scheme_disabled_by_default(self):
        assert os.path.isfile(self.FILE_PATH)
        r = self.request({'url': self.FILE_URL})
        self.assertStatusCode(r, 502)
        self.assertNotIn('script.js', r.text)

    def test_file_scheme_can_be_enabled(self):
        assert os.path.isfile(self.FILE_PATH)

        with SplashServer(extra_args=['--allowed-schemes=http,file']) as splash:
            url = splash.url('render.html')
            r = requests.get(url, params={'url': self.FILE_URL})

        self.assertStatusCode(r, 200)
        self.assertIn('script.js', r.text)

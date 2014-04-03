# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import shutil
import requests
from splash.tests import ts
from splash.tests.utils import TestServers
from splash.tests.test_render import BaseRenderTest


class BaseFiltersTest(BaseRenderTest):
    def assertFilters(self, resp, noscript, noscript2):
        # resp must be a response returned by a request to 'iframes'
        # endpoint of mock server
        if noscript:
            self.assertNotIn('SAME_DOMAIN', resp.text)
        else:
            self.assertIn('SAME_DOMAIN', resp.text)

        if noscript2:
            self.assertNotIn('OTHER_DOMAIN', resp.text)
        else:
            self.assertIn('OTHER_DOMAIN', resp.text)

    def params(self, **kwargs):
        kwargs.setdefault('url', ts.mockserver.url('iframes'))
        return kwargs


class FiltersTestHTML(BaseFiltersTest):

    def test_filtering_work(self):
        r = self.request(self.params())
        self.assertFilters(r, noscript=False, noscript2=False)

        r = self.request(self.params(filters='noscript'))
        self.assertFilters(r, noscript=True, noscript2=False)

        r = self.request(self.params(filters='noscript2'))
        self.assertFilters(r, noscript=False, noscript2=True)

    def test_multiple_filters(self):
        r = self.request(self.params(filters='noscript,noscript2'))
        self.assertFilters(r, noscript=True, noscript2=True)

    def test_invalid_filters(self):
        r = self.request(self.params(filters='foo,noscript2'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('foo', r.text)


class DefaultFiltersTest(BaseFiltersTest):
    def ts_request(self, ts2, query=None, render_format='html'):
        url = "http://localhost:%s/render.%s" % (ts2.splashserver.portnum, render_format)
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
            self.assertFilters(r, noscript=False, noscript2=False)

            # default.txt does not exist yet
            r = self.ts_request(ts2, {'filters': 'default'})
            self.assertEqual(r.status_code, 400)
            self.assertIn('default', r.text)

    def test_default_works(self):

        ts2 = TestServers()

        # create default.txt. It is the same as 'noscript.txt'.
        self.create_default_txt(ts2, copy_from='noscript.txt')

        with ts2:
            try:
                r = self.ts_request(ts2, {'filters': 'default'})
                self.assertFilters(r, noscript=True, noscript2=False)

                r = self.ts_request(ts2)
                self.assertFilters(r, noscript=True, noscript2=False)

                r = self.ts_request(ts2, {'filters': 'noscript'})
                self.assertFilters(r, noscript=True, noscript2=False)

                r = self.ts_request(ts2, {'filters': 'noscript2'})
                self.assertFilters(r, noscript=False, noscript2=True)

                r = self.ts_request(ts2, {'filters': 'noscript2,default'})
                self.assertFilters(r, noscript=True, noscript2=True)

                r = self.ts_request(ts2, {'filters': 'noscript,default'})
                self.assertFilters(r, noscript=True, noscript2=False)

                r = self.ts_request(ts2, {'filters': 'none'})
                self.assertFilters(r, noscript=False, noscript2=False)

            finally:
                self.remove_default_ini(ts2)


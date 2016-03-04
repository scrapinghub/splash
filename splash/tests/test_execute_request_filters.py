# -*- coding: utf-8 -*-
from __future__ import absolute_import

from splash.tests.test_execute import BaseLuaRenderTest
from splash.tests.test_request_filters import BaseFiltersTest


class ExecuteFiltersTest(BaseLuaRenderTest, BaseFiltersTest):

    def _lua_render_html(self, **kwargs):
        return self.request_lua("""
            function main(splash)
                assert(splash:go(splash.args.url))
                return splash:html()
            end
            """, self.params(**kwargs))

    def test_filters_applied_for_execute_endpoint(self):
        r = self._lua_render_html()
        self.assertFiltersWork(r, noscript=False, noscript2=False)

        r = self._lua_render_html(filters='noscript')
        self.assertFiltersWork(r, noscript=True, noscript2=False)

        r = self._lua_render_html(filters='noscript2')
        self.assertFiltersWork(r, noscript=False, noscript2=True)

    def test_no_url_argument(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.address))
            return splash:html()
        end
        """, dict(
            address=self.mockurl('iframes'),
            filters='noscript'
        ))
        self.assertFiltersWork(resp, noscript=True, noscript2=False)

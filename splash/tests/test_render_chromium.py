# -*- coding: utf-8 -*-
import pytest
from . import test_render


class ChromiumRequestHandler(test_render.DirectRequestHandler):
    engine = 'chromium'


class RenderHtmlTest(test_render.RenderHtmlTest):
    request_handler = ChromiumRequestHandler

    # FIXME: default certificate validation is too strict for tests
    https_supported = False

    @pytest.mark.xfail(reason="not implemented yet")
    def test_allowed_domains(self):
        super().test_allowed_domains()

    def test_viewport(self):
        r = self.request({'url': self.mockurl('jsviewport'), 'viewport': '300x400'})
        self.assertStatusCode(r, 200)
        # 300x400 is innerWidth/innerHeight
        # 300X400 would be outerWidth/outerHeight
        self.assertIn('300X400', r.text)

    @pytest.mark.xfail(reason="not implemented yet")
    def test_resource_timeout(self):
        super().test_resource_timeout()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_resource_timeout_abort_first(self):
        super().test_resource_timeout_abort_first()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_baseurl(self):
        super().test_baseurl()

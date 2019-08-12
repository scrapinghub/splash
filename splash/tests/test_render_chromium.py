# -*- coding: utf-8 -*-
import pytest
from . import test_render, test_redirects


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


class ChromiumRenderPngTest(test_render.RenderPngTest):
    request_handler = ChromiumRequestHandler

    # FIXME: default certificate validation is too strict for tests
    https_supported = False

    @pytest.mark.xfail(reason="not implemented yet")
    def test_images_enabled(self):
        super().test_images_enabled()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_images_disabled(self):
        super().test_images_disabled()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_render_all(self):
        super().test_render_all()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_render_all_with_viewport(self):
        super().test_render_all_with_viewport()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_resource_timeout(self):
        super().test_resource_timeout()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_resource_timeout_abort_first(self):
        super().test_resource_timeout_abort_first()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_very_long_green_page(self):
        super().test_very_long_green_page()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_viewport_full(self):
        super().test_viewport_full()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_viewport_full_wait(self):
        super().test_viewport_full_wait()

    @pytest.mark.xfail(reason="FIXME: why is it failing?")
    def test_scale_method_vector_produces_sharp_split(self):
        super().test_scale_method_vector_produces_sharp_split()

    @pytest.mark.xfail(reason="FIXME: why is it failing?")
    def test_scale_method_raster_produces_blurry_split(self):
        super().test_scale_method_raster_produces_blurry_split()


class ChromiumRenderJpegTest(test_render.RenderJpegTest):
    request_handler = ChromiumRequestHandler

    # FIXME: default certificate validation is too strict for tests
    https_supported = False

    @pytest.mark.xfail(reason="not implemented yet")
    def test_images_enabled(self):
        super().test_images_enabled()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_images_disabled(self):
        super().test_images_disabled()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_render_all(self):
        super().test_render_all()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_render_all_with_viewport(self):
        super().test_render_all_with_viewport()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_resource_timeout(self):
        super().test_resource_timeout()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_resource_timeout_abort_first(self):
        super().test_resource_timeout_abort_first()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_very_long_green_page(self):
        super().test_very_long_green_page()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_viewport_full(self):
        super().test_viewport_full()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_viewport_full_wait(self):
        super().test_viewport_full_wait()


class HttpRedirectTest(test_redirects.HttpRedirectTest):
    request_handler = ChromiumRequestHandler

    @pytest.mark.xfail(reason="not implemented yet")
    def test_301_baseurl(self):
        super().test_301_baseurl()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_302_baseurl(self):
        super().test_302_baseurl()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_303_baseurl(self):
        super().test_303_baseurl()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_307_baseurl(self):
        super().test_307_baseurl()


class MetaRedirectTest(test_redirects.MetaRedirectTest):
    request_handler = ChromiumRequestHandler


class JsRedirectTest(test_redirects.JsRedirectTest):
    request_handler = ChromiumRequestHandler

    @pytest.mark.skip(reason="In Chromium it is not guaranteed "
                             "JS redirects are not processed with wait=0")
    def test_redirect_nowait(self):
        pass

    @pytest.mark.xfail(reason="getting loadFinished=False, need to fix it")
    def test_redirect_slowimage_wait(self):
        super().test_redirect_slowimage_wait()

    @pytest.mark.xfail(reason="getting loadFinished=False, need to fix it. "
                              "Also, nowait is the same as wait here for "
                              "Chromium.")
    def test_redirect_slowimage_nowait(self):
        super().test_redirect_slowimage_nowait()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_redirect_slowimage_nowait_baseurl(self):
        super().test_redirect_slowimage_nowait_baseurl()

    @pytest.mark.xfail(reason="not implemented yet")
    def test_redirect_slowimage_wait_baseurl(self):
        super().test_redirect_slowimage_wait_baseurl()

    @pytest.mark.xfail(reason="behavior is different? "
                       "It seems error page is displayed instead of 502 code")
    def test_redirect_to_non_existing(self):
        super().test_redirect_to_non_existing()

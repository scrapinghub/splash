# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest

import pytest

from splash.lua import get_script_source
from . import test_render, test_redirects, test_har
from .utils import NON_EXISTING_RESOLVABLE


class Base:
    # a hack to skip test running from a mixin
    class EmulationMixin(test_render.BaseRenderTest):
        endpoint = 'execute'

        def request(self, query, endpoint=None, headers=None, **kwargs):
            query = {} or query
            query.update({'lua_source': self.script})
            return self._get_handler().request(query, endpoint, headers, **kwargs)

        def post(self, query, endpoint=None, payload=None, headers=None, **kwargs):
            raise NotImplementedError()

        # ==== overridden tests =============================
        @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
        def test_render_error(self):
            r = self.request({"url": "http://non-existent-host/"})
            self.assertStatusCode(r, 400)

        def test_self(self):
            # make sure mixin order is correct
            assert self.endpoint == 'execute'


class EmulatedRenderHtmlTest(Base.EmulationMixin, test_render.RenderHtmlTest):
    script = get_script_source("render_html.lua")


class EmulatedHttpRedirectTest(Base.EmulationMixin, test_redirects.HttpRedirectTest):
    script = get_script_source("render_html.lua")


class EmulatedJsRedirectTest(Base.EmulationMixin, test_redirects.JsRedirectTest):
    script = get_script_source("render_html.lua")

    # Overridden to return 400.
    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_redirect_to_non_existing(self):
        r = self.request({
            "url": self.mockurl("jsredirect-non-existing"),
            "wait": 0.2,
        })
        self.assertStatusCode(r, 400)


class EmulatedMetaRedirectTest(Base.EmulationMixin, test_redirects.MetaRedirectTest):
    script = get_script_source("render_html.lua")


class EmulatedRenderPngTest(Base.EmulationMixin, test_render.RenderPngTest):
    script = get_script_source("render_png.lua")

    # TODO: default width and height are not applied
    @pytest.mark.xfail
    def test_ok(self):
        super(EmulatedRenderPngTest, self).test_ok()

    @pytest.mark.xfail
    def test_ok_https(self):
        super(EmulatedRenderPngTest, self).test_ok_https()

    # TODO: fix validation
    @pytest.mark.xfail
    def test_viewport_out_of_bounds(self):
        super(EmulatedRenderPngTest, self).test_viewport_out_of_bounds()

    @pytest.mark.xfail
    def test_viewport_invalid(self):
        super(EmulatedRenderPngTest, self).test_viewport_invalid()

    @pytest.mark.xfail
    def test_range_checks(self):
        super(EmulatedRenderPngTest, self).test_range_checks()


class EmulatedRenderHarTest(Base.EmulationMixin, test_har.HarRenderTest):
    script = get_script_source("render_har.lua")

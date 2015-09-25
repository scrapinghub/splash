# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest

import pytest
lupa = pytest.importorskip("lupa")

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
            err = self.assertJsonError(r, 400)

        def test_self(self):
            # make sure mixin order is correct
            assert self.endpoint == 'execute'


class EmulatedRenderHtmlTest(Base.EmulationMixin, test_render.RenderHtmlTest):
    script = 'main = require("emulation").render_html'


class EmulatedHttpRedirectTest(Base.EmulationMixin, test_redirects.HttpRedirectTest):
    script = 'main = require("emulation").render_html'


class EmulatedJsRedirectTest(Base.EmulationMixin, test_redirects.JsRedirectTest):
    script = 'main = require("emulation").render_html'

    # Overridden to return 400.
    @unittest.skipIf(NON_EXISTING_RESOLVABLE, "non existing hosts are resolvable")
    def test_redirect_to_non_existing(self):
        r = self.request({
            "url": self.mockurl("jsredirect-non-existing"),
            "wait": 2.,
        })
        self.assertJsonError(r, 400)


class EmulatedMetaRedirectTest(Base.EmulationMixin, test_redirects.MetaRedirectTest):
    script = 'main = require("emulation").render_html'


class EmulatedRenderPngTest(Base.EmulationMixin, test_render.RenderPngTest):
    script = 'main = require("emulation").render_png'

    @pytest.mark.xfail(
        run=False,
        reason="""
Range validation in lua renderer is not implemented and out of range values of
width/height will consume huge amount of memory either bringing down the test
server because of OOM killer or grinding user system to a halt because of swap.
""")
    def test_range_checks(self):
        super(EmulatedRenderPngTest, self).test_range_checks()

    def test_extra_height_doesnt_leave_garbage_when_using_tiled_render(self):
        # XXX: this function belongs to test_render, BUT height < 1000 is fixed
        # in defaults and so is tile max size, so in order to force rendering
        # that may produce extra pixels at the bottom we go the way that avoids
        # parameter validation.
        r = self.request({'url': self.mockurl('tall'), 'viewport': '100x100',
                          'height': 3000})
        png = self.assertPng(r, height=3000)
        # Ensure that the extra pixels at the bottom are transparent.
        alpha_channel = png.crop((0, 100, 100, 3000)).getdata(3)
        self.assertEqual(alpha_channel.size, (100, 2900))
        self.assertEqual(alpha_channel.getextrema(), (0, 0))


class EmulatedRenderJpegTest(Base.EmulationMixin, test_render.RenderJpegTest):
    script = 'main = require("emulation").render_jpeg'

    @pytest.mark.xfail(
        run=False,
        reason="""
Range validation in lua renderer is not implemented and out of range values of
width/height will consume huge amount of memory either bringing down the test
server because of OOM killer or grinding user system to a halt because of swap.
""")
    def test_range_checks(self):
        super(EmulatedRenderJpegTest, self).test_range_checks()

    def test_extra_height_doesnt_leave_garbage_when_using_tiled_render(self):
        # XXX: this function belongs to test_render, BUT height < 1000 is fixed
        # in defaults and so is tile max size, so in order to force rendering
        # that may produce extra pixels at the bottom we go the way that avoids
        # parameter validation.
        r = self.request({'url': self.mockurl('tall'), 'viewport': '100x100',
                          'height': 3000})
        img = self.assertJpeg(r, height=3000)
        # Ensure that the extra pixels at the bottom are transparent.
        box = img.crop((0, 100, 100, 3000))
        self.assertEqual(box.size, (100, 2900))
        # iterate over channels
        for i in range(3):
            self.assertEqual(box.getdata(i).getextrema(), (255, 255))


class EmulatedRenderHarTest(Base.EmulationMixin, test_har.HarRenderTest):
    script = 'main = require("emulation").render_har'

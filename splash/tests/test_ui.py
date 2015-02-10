# -*- coding: utf-8 -*-
from __future__ import absolute_import
from splash import lua
from .test_render import BaseRenderTest


class UITest(BaseRenderTest):

    def test_render_ui_available(self):
        ui_main = self.request({}, endpoint="")
        self.assertStatusCode(ui_main, 200)
        self.assertIn("Splash", ui_main.text)

        if lua.is_supported():
            self.assertIn("<textarea", ui_main.text)
        else:
            self.assertNotIn("<textarea", ui_main.text)

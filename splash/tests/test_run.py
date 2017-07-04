# -*- coding: utf-8 -*-
from .test_execute import BaseLuaRenderTest

class BaseRunTest(BaseLuaRenderTest):
    endpoint = 'run'


class RunTest(BaseRunTest):
    def test_render(self):
        resp = self.request_lua("splash:go(args.url); return splash:html()",
                                {'url': self.mockurl('jsrender')})
        self.assertStatusCode(resp, 200)
        self.assertNotIn("Before", resp.text)
        self.assertIn("After", resp.text)

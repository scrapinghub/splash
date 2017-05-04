# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os, tempfile
import base64
import unittest
from io import BytesIO
import numbers
import time

from PIL import Image
import requests
import six
import pytest

lupa = pytest.importorskip("lupa")

from splash.exceptions import ScriptError
from splash.qtutils import qt_551_plus
from splash import __version__ as splash_version
from splash.har_builder import HarBuilder
from splash.har.utils import get_response_body_bytes

from . import test_render
from .test_jsonpost import JsonPostRequestHandler
from .utils import NON_EXISTING_RESOLVABLE, SplashServer
from .mockserver import JsRender
from .. import defaults


class BaseLuaRenderTest(test_render.BaseRenderTest):
    endpoint = 'execute'

    def request_lua(self, code, query=None, **kwargs):
        q = {"lua_source": code}
        q.update(query or {})
        return self.request(q, **kwargs)

    def assertScriptError(self, resp, subtype, message=None):
        err = self.assertJsonError(resp, 400, 'ScriptError')
        self.assertEqual(err['info']['type'], subtype)
        if message is not None:
            self.assertRegexpMatches(err['info']['message'], message)
        return err

    def assertErrorLineNumber(self, resp, line_number):
        self.assertEqual(resp.json()['info']['line_number'], line_number)


class UnsupportedContentTest(BaseLuaRenderTest):
    def test_download(self):
        d = tempfile.TemporaryDirectory()
        resp = self.request_lua("""
        function main(splash)
            splash.unsupported_content = 'download'
            splash.download_directory="%s"
            local d = splash.download_directory
            local u = splash.unsupported_content
            assert(splash:go("http://orimi.com/pdf-test.pdf"))
            return {png=splash:png()}
        end
        """ %(d.name,) )
        self.assertStatusCode(resp, 200)
        assert(os.path.isfile(os.path.join(d.name, 'pdf-test.pdf')))
        
        d.cleanup()
        
    def test_discard(self):
        resp = self.request_lua("""
        function main(splash)
            splash.unsupported_content = 'drop'
            assert(splash:go("http://orimi.com/pdf-test.pdf"))
            return {png=splash:png()}
        end
        """ )
        self.assertStatusCode(resp, 200)
        
    def test_undefined(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go("http://orimi.com/pdf-test.pdf"))
            return {png=splash:png()}
        end
        """ )
        self.assertStatusCode(resp, 400)
        


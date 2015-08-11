import json

import pytest

from .test_render import BaseRenderTest


class ContentTypeTest(BaseRenderTest):
    """Tests the content type middleware """
    endpoint = 'render.json'

    def _request(self, allowed_ctypes=None, forbidden_ctypes=None):
        js_source = """
        JSON.stringify({
            imageLoaded: window.imageLoaded,
            styleLoaded: getComputedStyle(document.body).backgroundColor == 'rgb(255, 0, 0)'
        });
        """
        query = {
            'url': self.mockurl("subresources/"),
            'script': 1,
            'console': 1,
            'js_source': js_source,
        }
        if allowed_ctypes is not None:
            query['allowed_content_types'] = allowed_ctypes

        if forbidden_ctypes is not None:
            query['forbidden_content_types'] = forbidden_ctypes

        req_headers = {'content-type': 'application/json'}
        response = self.post(query,
            endpoint=self.endpoint,
            payload=json.dumps(query),
            headers=req_headers
        ).json()['script']
        return json.loads(response)

    def test_disable(self):
        self.assertEqual(self._request(), {
            u'styleLoaded': True,
            u'imageLoaded': True
        })

    def test_block_css(self):
        self.assertEqual(self._request(forbidden_ctypes='text/css'), {
            u'styleLoaded': False,
            u'imageLoaded': True
        })

    def test_block_images(self):
        self.assertEqual(self._request(forbidden_ctypes='image/*'), {
            u'styleLoaded': True,
            u'imageLoaded': False
        })

    def test_block_both(self):
        self.assertEqual(self._request(forbidden_ctypes='image/*,text/css'), {
            u'styleLoaded': False,
            u'imageLoaded': False
        })

    def test_allow_images(self):
        self.assertEqual(self._request(allowed_ctypes='image/*,text/html'), {
            u'styleLoaded': False,
            u'imageLoaded': True
        })

    @pytest.mark.xfail(
        run=False,
        reason="https://github.com/scrapinghub/splash/issues/247")
    def test_dont_block_invalid(self):
        resp = self.request({"url": self.mockurl("bad-content-type")})
        self.assertEqual(resp.text, "ok")

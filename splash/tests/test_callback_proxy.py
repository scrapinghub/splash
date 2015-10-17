# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest

from splash.browser_tab import OneShotCallbackError, OneShotCallbackProxy


class OneShotCallbackProxyTest(unittest.TestCase):
    """
    The QTimer that OneShotCallbackProxy is based on won't work
    in a single-threaded unit test, so the timeout behavior isn't tested
    here; it is tested in test_execute.py::WaitForResume.
    """

    def setUp(self):
        # There's no mock library in the project, so we have a simple way
        # to count how many times our callback and errback are called.
        self._callback_count = 0
        self._errback_count = 0
        self._raise_count = 0

    def _make_proxy(self):
        def callback(val):
            self._callback_count += 1

        def errback(message, raise_):
            self._errback_count += 1

            if raise_:
                raise Exception()

        return OneShotCallbackProxy(None, callback, errback, timeout=0)

    def test_can_resume_once(self):
        cb_proxy = self._make_proxy()
        cb_proxy.resume('ok')
        self.assertEqual(self._callback_count, 1)
        self.assertEqual(self._errback_count, 0)

    def test_can_error_once(self):
        cb_proxy = self._make_proxy()
        cb_proxy.error('not ok')
        self.assertEqual(self._callback_count, 0)
        self.assertEqual(self._errback_count, 1)

    def test_can_error_with_raise(self):
        cb_proxy = self._make_proxy()

        with self.assertRaises(Exception):
            cb_proxy.error('not ok', raise_=True)

        self.assertEqual(self._callback_count, 0)
        self.assertEqual(self._errback_count, 1)

    def test_cannot_resume_twice(self):
        cb_proxy = self._make_proxy()
        cb_proxy.resume('ok')

        with self.assertRaises(OneShotCallbackError):
            cb_proxy.resume('still ok?')

    def test_cannot_resume_and_error(self):
        cb_proxy = self._make_proxy()
        cb_proxy.resume('ok')

        with self.assertRaises(OneShotCallbackError):
            cb_proxy.error('still ok?')

    def test_cannot_resume_after_cancel(self):
        cb_proxy = self._make_proxy()
        cb_proxy.cancel('changed my mind')

        with self.assertRaises(OneShotCallbackError):
            cb_proxy.resume('ok')

    def test_negative_timeout_is_invalid(self):
        with self.assertRaises(ValueError):
            cb_proxy = OneShotCallbackProxy(None, lambda a: a, lambda b: b, -1)

# -*- coding: utf-8 -*-
import unittest

from splash.browser_tab import OneShotCallbackProxy, _BrowserTabLogger


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

        class Logger(_BrowserTabLogger):
            def __init__(self, uid, verbosity):
                self.messages = []
                super().__init__(uid, verbosity)

            def log(self, message, min_level=None):
                self.messages.append((message, min_level))
                super().log(message, min_level)

        logger = Logger(uid=0, verbosity=2)
        return OneShotCallbackProxy(None, callback, errback, logger, timeout=0)

    def _assertLastMessageWarns(self, cb_proxy: OneShotCallbackProxy):
        assert cb_proxy.logger.messages[-1][1] == 1

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

        cb_proxy.resume('still ok?')
        self._assertLastMessageWarns(cb_proxy)

    def test_cannot_resume_and_error(self):
        cb_proxy = self._make_proxy()
        cb_proxy.resume('ok')
        cb_proxy.error('still ok?')
        self._assertLastMessageWarns(cb_proxy)

    def test_cannot_resume_after_cancel(self):
        cb_proxy = self._make_proxy()
        cb_proxy.cancel('changed my mind')
        cb_proxy.resume('ok')
        self._assertLastMessageWarns(cb_proxy)

    def test_negative_timeout_is_invalid(self):
        with self.assertRaises(ValueError):
            logger = _BrowserTabLogger(uid=0, verbosity=2)
            cb_proxy = OneShotCallbackProxy(None, lambda a: a, lambda b: b,
                                            logger, -1)

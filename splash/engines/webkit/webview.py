# -*- coding: utf-8 -*-
from PyQt5.QtWebKitWidgets import QWebView


class SplashQWebView(QWebView):
    """
    QWebView subclass that handles 'close' requests. By default,
    it prevents closing.
    """
    onBeforeClose = None

    def closeEvent(self, event):
        dont_close = False
        if self.onBeforeClose:
            dont_close = self.onBeforeClose()

        if dont_close:
            event.ignore()
        else:
            event.accept()



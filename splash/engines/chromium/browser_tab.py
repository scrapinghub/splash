# -*- coding: utf-8 -*-
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
from PyQt5.QtCore import (
    QObject, QSize, Qt, QTimer, pyqtSlot, QEvent,
    QPointF, QPoint, pyqtSignal, QUrl,
)
from twisted.internet import defer


from splash.browser_tab import BrowserTab, skip_if_closing
from splash.qtutils import WrappedSignal
from splash.errors import RenderErrorInfo

from .webpage import ChromiumWebPage
from .constants import RenderProcessTerminationStatus


class ChromiumBrowserTab(BrowserTab):
    def __init__(self, render_options, verbosity):
        super().__init__(render_options, verbosity)
        self.profile = QWebEngineProfile()  # don't share cookies
        self.web_page = ChromiumWebPage(self.profile)
        self.web_view = QWebEngineView()
        self.web_view.setPage(self.web_page)

        self._setup_webpage_events()
        self._html_d = None

    def _setup_webpage_events(self):
        self._load_finished = WrappedSignal(self.web_view.loadFinished)
        self._render_terminated = WrappedSignal(self.web_view.renderProcessTerminated)

        self.web_view.renderProcessTerminated.connect(self._on_render_terminated)
        self.web_view.loadFinished.connect(self._on_load_finished)
        # main_frame.urlChanged.connect(self._on_url_changed)
        # main_frame.javaScriptWindowObjectCleared.connect(
        #     self._on_javascript_window_object_cleared)
        # self.logger.add_web_page(self.web_page)

    def go(self, url, callback, errback):
        callback_id = self._load_finished.connect(
            self._on_content_ready,
            callback=callback,
            errback=errback,
        )
        self.logger.log("callback %s is connected to loadFinished" % callback_id, min_level=3)
        self.web_view.load(QUrl(url))

    @skip_if_closing
    def _on_content_ready(self, ok, callback, errback, callback_id):
        """
        This method is called when a QWebEnginePage finishes loading.
        """
        self.logger.log("loadFinished: disconnecting callback %s" % callback_id,
                        min_level=3)
        self._load_finished.disconnect(callback_id)
        if ok:
            callback()
        else:
            error_info = RenderErrorInfo(
                type='Unknown',
                code=0,
                text="loadFinished ok=False",
                url=self.web_view.url().toString()
            )
            errback(error_info)

    def _on_load_finished(self, ok):
        self.logger.log("loadFinished, ok=%s" % ok)

    def _on_render_terminated(self, status, code):
        status_details = RenderProcessTerminationStatus.get(status, 'unknown')
        self.logger.log("renderProcessTerminated: %s (%s), exit_code=%s" % (
            status, status_details, code), min_level=1)

    def html(self):
        """ Return HTML of the current main frame """
        self.logger.log("getting HTML", min_level=2)
        if self._html_d is not None:
            self.logger.log("HTML is already requested", min_level=1)
            return self._html_d
        self._html_d = defer.Deferred()
        self.web_view.page().toHtml(self._on_html_ready)
        return self._html_d

    def _on_html_ready(self, html):
        self.logger.log("HTML ready", min_level=2)
        self._html_d.callback(html)
        self._html_d = None

    def stop_loading(self):
        self.logger.log("stop_loading", min_level=2)
        self.web_view.stop()

    @skip_if_closing
    def close(self):
        """ Destroy this tab """
        super().close()
        self.web_view.stop()
        self.web_view.close()
        self.web_page.deleteLater()
        self.web_view.deleteLater()

        # TODO
        # self._cancel_all_timers()

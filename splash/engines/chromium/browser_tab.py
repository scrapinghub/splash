# -*- coding: utf-8 -*-
import base64

from PyQt5.QtWebEngineWidgets import (
    QWebEngineView,
    QWebEngineProfile,
    QWebEngineSettings
)
from PyQt5.QtCore import (
    QObject, QSize, Qt, QTimer, pyqtSlot, QEvent,
    QPointF, QPoint, pyqtSignal, QUrl,
    QSizeF,
)
from twisted.internet import defer

from splash import defaults
from splash.browser_tab import (
    BrowserTab,
    skip_if_closing,
    webpage_option_setter,
    webpage_option_getter
)
from splash.qtutils import WrappedSignal, parse_size
from splash.errors import RenderErrorInfo
from splash.render_options import validate_size_str

from .webpage import ChromiumWebPage
from .constants import RenderProcessTerminationStatus
from .screenshot import QtChromiumScreenshotRenderer


class ChromiumBrowserTab(BrowserTab):
    def __init__(self, render_options, verbosity):
        super().__init__(render_options, verbosity)
        self.profile = QWebEngineProfile()  # don't share cookies
        self.web_page = ChromiumWebPage(self.profile)
        self.web_view = QWebEngineView()
        self.web_view.setPage(self.web_page)

        self.web_view.setAttribute(Qt.WA_DeleteOnClose, True)

        # TODO: is it ok? :)
        # self.web_view.setAttribute(Qt.WA_DontShowOnScreen, True)

        # FIXME: required for screenshots?
        # Also, without .show() in JS window.innerWidth/innerHeight are zeros
        self.web_view.show()

        self._setup_webpage_events()
        self._set_default_webpage_options()
        self._html_d = None

        # ensure that default window size is not 640x480.
        self.set_viewport(defaults.VIEWPORT_SIZE)

    def _setup_webpage_events(self):
        self._load_finished = WrappedSignal(self.web_view.loadFinished)
        self._render_terminated = WrappedSignal(self.web_view.renderProcessTerminated)

        self.web_view.renderProcessTerminated.connect(self._on_render_terminated)
        self.web_view.loadFinished.connect(self._on_load_finished)
        # main_frame.urlChanged.connect(self._on_url_changed)
        # main_frame.javaScriptWindowObjectCleared.connect(
        #     self._on_javascript_window_object_cleared)
        # self.logger.add_web_page(self.web_page)

    def _set_default_webpage_options(self):
        """ Set QWebPage options. TODO: allow to customize defaults. """
        settings = self.web_page.settings()
        settings.setAttribute(QWebEngineSettings.ScreenCaptureEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.ShowScrollBars, False)

        # TODO
        # if self.visible:
        #     settings.setAttribute(QWebSettings.DeveloperExtrasEnabled, True)

        # TODO: options
        # self.set_js_enabled(True)
        # self.set_plugins_enabled(defaults.PLUGINS_ENABLED)
        # self.set_request_body_enabled(defaults.REQUEST_BODY_ENABLED)
        # self.set_response_body_enabled(defaults.RESPONSE_BODY_ENABLED)
        # self.set_indexeddb_enabled(defaults.INDEXEDDB_ENABLED)
        # self.set_webgl_enabled(defaults.WEBGL_ENABLED)
        # self.set_html5_media_enabled(defaults.HTML5_MEDIA_ENABLED)
        # self.set_media_source_enabled(defaults.MEDIA_SOURCE_ENABLED)

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
        self.logger.log("loadFinished, ok=%s" % ok, min_level=2)

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

    def png(self, width=None, height=None, b64=False, render_all=False,
            scale_method=None, region=None):
        """ Return screenshot in PNG format """
        # FIXME: move to base class
        self.logger.log(
            "Getting PNG: width=%s, height=%s, "
            "render_all=%s, scale_method=%s, region=%s" %
            (width, height, render_all, scale_method, region), min_level=2)
        if render_all:
            raise ValueError("render_all=True is not supported yet")

        image = self._get_image('PNG', width, height, render_all,
                                scale_method, region=region)
        result = image.to_png()
        if b64:
            result = base64.b64encode(result).decode('utf-8')
        # self.store_har_timing("_onPngRendered")
        return result

    def jpeg(self, width=None, height=None, b64=False, render_all=False,
             scale_method=None, quality=None, region=None):
        """ Return screenshot in JPEG format. """
        # FIXME: move to base class
        self.logger.log(
            "Getting JPEG: width=%s, height=%s, "
            "render_all=%s, scale_method=%s, quality=%s, region=%s" %
            (width, height, render_all, scale_method, quality, region),
            min_level=2)
        if render_all:
            raise ValueError("render_all=True is not supported yet")

        image = self._get_image('JPEG', width, height, render_all,
                                scale_method, region=region)
        result = image.to_jpeg(quality=quality)
        if b64:
            result = base64.b64encode(result).decode('utf-8')
        # self.store_har_timing("_onJpegRendered")
        return result

    def _get_image(self, image_format, width, height, render_all,
                   scale_method, region):
        renderer = QtChromiumScreenshotRenderer(
            self.web_page, self.logger, image_format,
            width=width, height=height, scale_method=scale_method,
            region=region)
        return renderer.render_qwebpage()

    def set_viewport(self, size, raise_if_empty=False):
        """
        Set viewport size.
        If size is "full" viewport size is detected automatically.
        If can also be "<width>x<height>".

        FIXME: Currently the implementation just resizes the window, which
        causes Splash to crash on large sizes(?).
        Actully it is not changing the viewport.

        XXX: As an effect, this function changes window.outerWidth/outerHeight,
        while in Webkit implementation window.innerWidth/innerHeight
        is changed.
        """
        if size == 'full':
            size = self.web_page.contentsSize()
            self.logger.log("Contents size: %s" % size, min_level=2)
            if size.isEmpty():
                if raise_if_empty:
                    raise RuntimeError("Cannot detect viewport size")
                else:
                    size = defaults.VIEWPORT_SIZE
                    self.logger.log("Viewport is empty, falling back to: %s" %
                                    size)

        if not isinstance(size, (QSize, QSizeF)):
            validate_size_str(size)
            size = parse_size(size)
        w, h = int(size.width()), int(size.height())

        # XXX: it was crashing with large windows, but then the problem
        # seemed to go away. Need to keep an eye on it.
        # # FIXME: don't resize the window?
        # # FIXME: figure out exact limits
        # MAX_WIDTH = 1280
        # MAX_HEIGHT = 1920
        #
        # if w > MAX_WIDTH:
        #     raise RuntimeError("Width {} > {} is currently prohibited".format(
        #         w, MAX_WIDTH
        #     ))
        #
        # if h > MAX_HEIGHT:
        #     raise RuntimeError("Height {} > {} is currently prohibited".format(
        #         h, MAX_HEIGHT
        #     ))
        self.web_view.resize(w, h)

        # self._force_relayout()
        self.logger.log("viewport size is set to %sx%s" % (w, h), min_level=2)
        self.logger.log("real viewport size: %s" % self.web_view.size(), min_level=2)
        return w, h

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

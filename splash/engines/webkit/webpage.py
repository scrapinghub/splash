# -*- coding: utf-8 -*-

import sip
from PyQt5.QtWebKitWidgets import QWebPage
from PyQt5.QtCore import QByteArray
from twisted.python import log
import traceback

from splash.browser_tab import WebpageEventLogger
from splash.har_builder import HarBuilder
from splash.errors import RenderErrorInfo
from splash.qtutils import qurl2ascii


class WebkitWebPage(QWebPage):
    """
    QWebPage subclass that:

    * changes user agent;
    * logs JS console messages;
    * handles alert, confirm and prompt windows;
    * returns additional info about render errors;
    * logs HAR events;
    * stores options for various Splash components.
    """
    error_info = None
    custom_user_agent = None
    custom_headers = None
    skip_custom_headers = False
    navigation_locked = False
    resource_timeout = 0
    request_body_enabled = False
    response_body_enabled = False
    http2_enabled = False

    def __init__(self, verbosity=0):
        super(QWebPage, self).__init__()
        self.verbosity = verbosity
        self.callbacks = {
            "on_request": [],
            "on_response_headers": [],
            "on_response": [],
            "on_navigation_locked": [],
        }
        self.mainFrame().urlChanged.connect(self.on_url_changed)
        self.mainFrame().titleChanged.connect(self.on_title_changed)
        self.mainFrame().loadFinished.connect(self.on_load_finished)
        self.mainFrame().initialLayoutCompleted.connect(self.on_layout_completed)
        self.har = HarBuilder()

    def reset_har(self):
        self.har.reset()

    def run_callbacks(self, event_name, *args):
        for cb in self.callbacks.get(event_name, []):
            try:
                cb(*args)
            except:
                # TODO unhandled exceptions in lua callbacks
                # should we raise errors here?
                # https://github.com/scrapinghub/splash/issues/161
                log.msg("error in %s callback" % event_name)
                log.msg(traceback.format_exc())

    def clear_callbacks(self, event=None):
        """
        Unregister all callbacks for an event. If event is None
        then all callbacks are removed.
        """
        if event is None:
            for ev in self.callbacks:
                assert ev is not None
                self.clear_callbacks(ev)
            return
        del self.callbacks[event][:]

    def on_title_changed(self, title):
        self.har.store_title(title)

    def on_url_changed(self, url):
        self.har.store_url(url)

    def on_load_finished(self, ok):
        self.har.store_timing("onLoad")

    def on_layout_completed(self):
        self.har.store_timing("onContentLoad")

    def acceptNavigationRequest(self, webFrame, networkRequest, navigationType):
        if self.navigation_locked:
            self.run_callbacks('on_navigation_locked', networkRequest)
            return False
        self.error_info = None
        return super(WebkitWebPage, self).acceptNavigationRequest(webFrame, networkRequest, navigationType)

    def javaScriptAlert(self, frame, msg):
        return

    def javaScriptConfirm(self, frame, msg):
        return False

    def javaScriptPrompt(self, frame, msg, default=None):
        if self.verbosity >= 2:
            log.msg("javaScriptPrompt, url=%s, msg=%r, default=%r" % (
                    frame.url().toString(), msg, default))
        return False, ""  # thanks qutebrowser

    def javaScriptConsoleMessage(self, msg, line_number, source_id):
        if self.verbosity >= 2:
            log.msg("JsConsole(%s:%d): %s" % (source_id, line_number, msg), system='render')

    def userAgentForUrl(self, url):
        if self.custom_user_agent is None:
            return super(WebkitWebPage, self).userAgentForUrl(url)
        else:
            return self.custom_user_agent

    # loadFinished signal handler receives ok=False at least these cases:
    # 1. when there is an error with the page (e.g. the page is not available);
    # 2. when a redirect happened before all related resource are loaded;
    # 3. when page sends headers that are not parsed correctly
    #    (e.g. a bad Content-Type).
    # By implementing ErrorPageExtension we can catch (1) and
    # distinguish it from (2) and (3).
    def extension(self, extension, info=None, errorPage=None):
        if extension == QWebPage.ErrorPageExtension:
            if self.verbosity >= 2:
                log.msg("ErrorPageExtension in WebkitWebPage.extension")
            # catch the error, populate self.errorInfo and return an error page

            info = sip.cast(info, QWebPage.ErrorPageExtensionOption)

            domain = 'Unknown'
            if info.domain == QWebPage.QtNetwork:
                domain = 'Network'
            elif info.domain == QWebPage.Http:
                domain = 'HTTP'
            elif info.domain == QWebPage.WebKit:
                domain = 'WebKit'

            self.error_info = RenderErrorInfo(
                type=domain,
                code=int(info.error),
                text=str(info.errorString),
                url=str(info.url.toString())
            )

            # XXX: this page currently goes nowhere
            content = u"""
                <html><head><title>Failed loading page</title></head>
                <body>
                    <h1>Failed loading page ({0.text})</h1>
                    <h2>{0.url}</h2>
                    <p>{0.type} error #{0.code}</p>
                </body></html>""".format(self.error_info)

            errorPage = sip.cast(errorPage, QWebPage.ErrorPageExtensionReturn)
            errorPage.content = QByteArray(content.encode('utf-8'))
            return True

        # XXX: this method always returns True, even if we haven't
        # handled the extension. Is it correct? When can this method be
        # called with extension which is not ErrorPageExtension if we
        # are returning False in ``supportsExtension`` for such extensions?
        if self.verbosity >= 1:
            log.msg("Unhandled condition in WebkitWebPage.extension")
        return True

    def supportsExtension(self, extension):
        if extension == QWebPage.ErrorPageExtension:
            return True
        return False

    def maybe_redirect(self, load_finished_ok):
        """
        Return True if the current webpage state looks like a redirect.
        Use this function from loadFinished handler to ignore spurious
        signals.

        FIXME: This can return True if server returned incorrect
        Content-Type header, but there is no an additional loadFinished
        signal in this case.
        """
        return not load_finished_ok and self.error_info is None

    def is_ok(self, load_finished_ok):
        return load_finished_ok and self.error_info is None

    def error_loading(self, load_finished_ok):
        return load_finished_ok and self.error_info is not None


class WebkitEventLogger(WebpageEventLogger):
    """ This class logs various events that happen with QWebPage """
    def add_web_page(self, web_page: WebkitWebPage) -> None:
        frame = web_page.mainFrame()
        # setup logging
        if self.logger.verbosity >= 4:
            web_page.loadStarted.connect(self.on_load_started)
            frame.loadFinished.connect(self.on_frame_load_finished)
            frame.loadStarted.connect(self.on_frame_load_started)
            frame.contentsSizeChanged.connect(self.on_contents_size_changed)
            # TODO: on_repaint

        if self.logger.verbosity >= 3:
            frame.javaScriptWindowObjectCleared.connect(self.on_javascript_window_object_cleared)
            frame.initialLayoutCompleted.connect(self.on_initial_layout_completed)
            frame.urlChanged.connect(self.on_url_changed)

    def on_load_started(self):
        self.logger.log("loadStarted")

    def on_frame_load_finished(self, ok):
        self.logger.log("mainFrame().LoadFinished %s" % ok)

    def on_frame_load_started(self):
        self.logger.log("mainFrame().loadStarted")

    def on_contents_size_changed(self, sz):
        self.logger.log("mainFrame().contentsSizeChanged: %s" % sz)

    def on_javascript_window_object_cleared(self):
        self.logger.log("mainFrame().javaScriptWindowObjectCleared")

    def on_initial_layout_completed(self):
        self.logger.log("mainFrame().initialLayoutCompleted")

    def on_url_changed(self, url):
        self.logger.log("mainFrame().urlChanged %s" % qurl2ascii(url))


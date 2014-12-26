# -*- coding: utf-8 -*-
from __future__ import absolute_import
import pprint
from collections import namedtuple
import sip
from PyQt4.QtWebKit import QWebPage
from PyQt4.QtCore import QByteArray
from twisted.python import log
from splash.cookies import SplashCookieJar
from splash.har.log import HarLog


RenderErrorInfo = namedtuple('RenderErrorInfo', 'type code text url')


class SplashQWebPage(QWebPage):
    """
    QWebPage subclass that:

    * changes user agent;
    * logs JS console messages;
    * handles alert and confirm windows;
    * returns additional info about render errors;
    * logs HAR events.
    """
    error_info = None
    custom_user_agent = None
    custom_headers = None
    skip_custom_headers = False
    navigation_locked = False

    def __init__(self, verbosity=0):
        super(QWebPage, self).__init__()
        self.verbosity = verbosity
        self.har_log = HarLog()
        self.cookiejar = SplashCookieJar(self)

        self.mainFrame().urlChanged.connect(self.onUrlChanged)
        self.mainFrame().titleChanged.connect(self.onTitleChanged)
        self.mainFrame().loadFinished.connect(self.onLoadFinished)
        self.mainFrame().initialLayoutCompleted.connect(self.onLayoutCompleted)

    def onTitleChanged(self, title):
        self.har_log.store_title(title)

    def onUrlChanged(self, url):
        self.har_log.store_url(url.toString())

    def onLoadFinished(self, ok):
        self.har_log.store_timing("onLoad")

    def onLayoutCompleted(self):
        self.har_log.store_timing("onContentLoad")

    def acceptNavigationRequest(self, webFrame, networkRequest, navigationType):
        if self.navigation_locked:
            return False
        return super(SplashQWebPage, self).acceptNavigationRequest(webFrame, networkRequest, navigationType)

    def javaScriptAlert(self, frame, msg):
        return

    def javaScriptConfirm(self, frame, msg):
        return False

    def javaScriptConsoleMessage(self, msg, line_number, source_id):
        if self.verbosity >= 2:
            log.msg("JsConsole(%s:%d): %s" % (source_id, line_number, msg), system='render')

    def userAgentForUrl(self, url):
        if self.custom_user_agent is None:
            return super(SplashQWebPage, self).userAgentForUrl(url)
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
                domain,
                int(info.error),
                unicode(info.errorString),
                unicode(info.url.toString())
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

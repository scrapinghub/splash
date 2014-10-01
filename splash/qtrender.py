from __future__ import absolute_import
import os
import json
import base64
import copy
import datetime
from collections import namedtuple
import sip
from PyQt4.QtWebKit import QWebPage, QWebSettings, QWebView, qWebKitVersion
from PyQt4.QtCore import (Qt, QUrl, QBuffer, QSize, QTimer, QObject,
                          pyqtSlot, QByteArray, PYQT_VERSION_STR, QT_VERSION_STR)
from PyQt4.QtGui import QPainter, QImage
from PyQt4.QtNetwork import QNetworkRequest, QNetworkAccessManager
from twisted.internet import defer
from twisted.python import log
import splash
from splash import defaults
from splash.qtutils import qurl2ascii
from splash import har


class RenderError(Exception):
    pass


RenderErrorInfo = namedtuple('RenderErrorInfo', 'type code text url')


class SplashQWebPage(QWebPage):
    """
    QWebPage subclass that:

    * changes user agent;
    * logs JS console messages;
    * handles alert and confirm windows;
    * returns additional info about render errors.
    """
    errorInfo = None

    custom_user_agent = None

    def __init__(self, verbosity=0):
        super(QWebPage, self).__init__()
        self.verbosity = verbosity
        self.network_entries_map = {}
        self.created_at = datetime.datetime.utcnow()
        self.page_id = "page_0"
        self.har_page_info = {
            "startedDateTime": har.format_datetime(self.created_at),
            "id": self.page_id,
            "pageTimings": {
                "onContentLoad": -1,
                "onLoad": -1,
            },
        }

        self.mainFrame().titleChanged.connect(self.onTitleChanged)
        self.mainFrame().loadFinished.connect(self.onLoadFinished)
        self.mainFrame().initialLayoutCompleted.connect(self.onLayoutCompleted)

    def onTitleChanged(self, title):
        self.har_page_info['title'] = unicode(title)

    def onLoadFinished(self, ok):
        self.logEvent("onLoad")

    def onLayoutCompleted(self):
        self.logEvent("onContentLoad")

    def logEvent(self, name):
        self.har_page_info["pageTimings"][name] = har.get_duration(self.created_at)

    @property
    def network_entries(self):
        # FIXME: use OrderedDict to maintain the order?
        keys = sorted(self.network_entries_map.keys())
        entries = [self.network_entries_map[key] for key in keys]
        return [
            {k:v for (k,v) in entry.items() if not k.startswith('_')}
            for entry in entries
        ]

    def last_network_entry(self, url):
        if isinstance(url, QUrl):
            url = unicode(url.toString())

        for entry in reversed(self.network_entries):
            if entry['request']['url'] == url:
                return entry

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

            self.errorInfo = RenderErrorInfo(
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
                </body></html>""".format(self.errorInfo)

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


class WebpageRender(object):
    """
    WebpageRender object renders a webpage: it downloads the page using
    network_manager and renders it using QWebView according to options
    passed to :meth:`WebpageRender.doRequest`.

    This class is not used directly; its subclasses are used.
    Subclasses choose how to return the result (as html, json, png).
    """
    def __init__(self, network_manager, splash_proxy_factory, splash_request, verbosity):
        self.network_manager = network_manager
        self.web_view = QWebView()
        self.web_page = SplashQWebPage(verbosity)
        self.web_page.setNetworkAccessManager(self.network_manager)
        self.web_view.setPage(self.web_page)
        self.web_view.setAttribute(Qt.WA_DeleteOnClose, True)
        settings = self.web_page.settings()
        settings.setAttribute(QWebSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebSettings.PluginsEnabled, False)
        settings.setAttribute(QWebSettings.PrivateBrowsingEnabled, True)
        settings.setAttribute(QWebSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebSettings.LocalContentCanAccessRemoteUrls, True)
        self.web_page.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        self.web_page.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)

        self.splash_request = splash_request
        self.web_page.splash_request = splash_request
        self.web_page.splash_proxy_factory = splash_proxy_factory
        self.verbosity = verbosity

        self.deferred = defer.Deferred()

    # ======= General request/response handling:

    def doRequest(self, url, baseurl=None, wait_time=None, viewport=None,
                  js_source=None, js_profile=None, images=None, console=False):
        self.url = url
        self.history = []
        self.wait_time = defaults.WAIT_TIME if wait_time is None else wait_time
        self.js_source = js_source
        self.js_profile = js_profile
        self.console = console
        self.viewport = defaults.VIEWPORT if viewport is None else viewport

        self.web_page.settings().setAttribute(QWebSettings.AutoLoadImages, images)

        # setup logging
        if self.verbosity >= 4:
            self.web_page.loadStarted.connect(self._loadStarted)
            self.web_page.mainFrame().loadFinished.connect(self._frameLoadFinished)
            self.web_page.mainFrame().loadStarted.connect(self._frameLoadStarted)
            self.web_page.mainFrame().contentsSizeChanged.connect(self._contentsSizeChanged)

        if self.verbosity >= 3:
            self.web_page.mainFrame().javaScriptWindowObjectCleared.connect(self._javaScriptWindowObjectCleared)
            self.web_page.mainFrame().initialLayoutCompleted.connect(self._initialLayoutCompleted)

        self.web_page.mainFrame().urlChanged.connect(self._urlChanged)

        # do the request
        request = QNetworkRequest()
        request.setUrl(QUrl(url.decode('utf8')))

        if self.viewport != 'full':
            # viewport='full' can't be set if content is not loaded yet
            self._setViewportSize(self.viewport)

        if getattr(self.splash_request, 'pass_headers', False):
            headers = self.splash_request.getAllHeaders()
            for name, value in headers.items():
                request.setRawHeader(name, value)
                if name.lower() == 'user-agent':
                    self.web_page.custom_user_agent = value

        if baseurl:
            # If baseurl is used, we download the page manually,
            # then set its contents to the QWebPage and let it
            # download related resources and render the result.
            self._baseUrl = QUrl(baseurl.decode('utf8'))
            request.setOriginatingObject(self.web_page.mainFrame())
            self._reply = self.network_manager.get(request)
            self._reply.finished.connect(self._requestFinished)
        else:
            self.web_page.loadFinished.connect(self._loadFinished)

            if self.splash_request.method == 'POST':
                body = self.splash_request.content.getvalue()
                self.web_page.mainFrame().load(
                    request, QNetworkAccessManager.PostOperation, body
                )
            else:
                self.web_page.mainFrame().load(request)

        self.web_page.logEvent("_onStarted")

    def render(self):
        """
        This method is called to get the result after the requested page is
        downloaded and rendered. Subcalles should implement it to customize
        which data to return.
        """
        raise NotImplementedError()

    def close(self):
        """
        This method is called by a Pool after the rendering is done and
        the WebpageRender object is no longer needed.
        """
        self.web_view.stop()
        self.web_view.close()
        self.web_page.deleteLater()
        self.web_view.deleteLater()

    def _requestFinished(self):
        """
        This method is called when ``baseurl`` is used and a
        reply for the first request is received.
        """
        self.log("_requestFinished %s" % id(self.splash_request))
        self.web_page.loadFinished.connect(self._loadFinished)
        mimeType = self._reply.header(QNetworkRequest.ContentTypeHeader).toString()
        data = self._reply.readAll()
        self.web_page.mainFrame().setContent(data, mimeType, self._baseUrl)
        if self._reply.error():
            self.log("Error loading %s: %s" % (self.url, self._reply.errorString()), min_level=1)
        self._reply.close()
        self._reply.deleteLater()

    def _loadFinished(self, ok):
        """
        This method is called when a QWebPage finished loading its contents.
        """
        if self.deferred.called:
            # sometimes this callback is called multiple times
            self.log("loadFinished called multiple times", min_level=1)
            return

        page_ok = ok and self.web_page.errorInfo is None
        maybe_redirect = not ok and self.web_page.errorInfo is None
        error_loading = ok and self.web_page.errorInfo is not None

        if maybe_redirect:
            self.log("Redirect or other non-fatal error detected %s" % id(self.splash_request))
            # XXX: It assumes loadFinished will be called again because
            # redirect happens. If redirect is detected improperly,
            # loadFinished won't be called again, and Splash will return
            # the result only after a timeout.
            #
            # FIXME: This can happen if server returned incorrect
            # Content-Type header; there is no an additional loadFinished
            # signal in this case.
            return

        if page_ok:
            time_ms = int(self.wait_time * 1000)
            self.log("loadFinished %s; waiting %sms" % (id(self.splash_request), time_ms))
            QTimer.singleShot(time_ms, self._loadFinishedOK)
        elif error_loading:
            self.log("loadFinished %s: %s" % (id(self.splash_request), str(self.web_page.errorInfo)), min_level=1)
            # XXX: maybe return a meaningful error page instead of generic
            # error message?
            self.deferred.errback(RenderError())
        else:
            self.log("loadFinished %s: unknown error" % id(self.splash_request), min_level=1)
            self.deferred.errback(RenderError())

    def _loadFinishedOK(self):
        self.log("_loadFinishedOK %s" % id(self.splash_request))
        self.web_page.logEvent("_onPrepareStart")
        try:
            self._prepareRender()
            self.deferred.callback(self.render())
        except:
            self.deferred.errback()

    def _frameLoadFinished(self, ok):
        self.log("mainFrame().LoadFinished %s %s" % (id(self.splash_request), ok), min_level=4)

    def _loadStarted(self):
        self.log("loadStarted %s" % id(self.splash_request), min_level=4)

    def _urlChanged(self, url):
        self.history.append(self.web_page.last_network_entry(url))
        msg = "mainFrame().urlChanged %s: %s" % (id(self.splash_request), qurl2ascii(url))
        self.log(msg, min_level=4)

    def _frameLoadStarted(self):
        self.log("mainFrame().loadStarted %s" % id(self.splash_request), min_level=4)

    def _initialLayoutCompleted(self):
        self.log("mainFrame().initialLayoutCompleted %s" % id(self.splash_request), min_level=3)

    def _javaScriptWindowObjectCleared(self):
        self.log("mainFrame().javaScriptWindowObjectCleared %s" % id(self.splash_request), min_level=3)

    def _contentsSizeChanged(self):
        self.log("mainFrame().contentsSizeChanged %s" % id(self.splash_request), min_level=4)

    def _repaintRequested(self):
        self.log("mainFrame().repaintRequested %s" % id(self.splash_request), min_level=4)

    # ======= Rendering methods that subclasses can use:

    def _getHtml(self):
        self.log("getting HTML %s" % id(self.splash_request))
        frame = self.web_page.mainFrame()
        result = bytes(frame.toHtml().toUtf8())
        self.web_page.logEvent("_onHtmlRendered")
        return result

    def _getPng(self, width=None, height=None, b64=False):
        self.log("getting PNG %s" % id(self.splash_request))

        image = QImage(self.web_page.viewportSize(), QImage.Format_ARGB32)
        painter = QPainter(image)
        self.web_page.mainFrame().render(painter)
        painter.end()
        self.web_page.logEvent("_onScreenshotPrepared")

        if width:
            image = image.scaledToWidth(width, Qt.SmoothTransformation)
        if height:
            image = image.copy(0, 0, width, height)
        b = QBuffer()
        image.save(b, "png")
        result = bytes(b.data())
        if b64:
            result = base64.b64encode(result)
        self.web_page.logEvent("_onPngRendered")
        return result

    def _getIframes(self, children=True, html=True):
        self.log("getting iframes %s" % id(self.splash_request))
        frame = self.web_page.mainFrame()
        result = self._frameToDict(frame, children, html)
        self.web_page.logEvent("_onIframesRendered")
        return result

    def _getHistory(self):
        hist = copy.deepcopy(self.history)
        for entry in hist:
            if entry is not None:
                del entry['request']['queryString']
        return hist

    def _getHAR(self):
        res = {
            "log": {
                "version" : "1.2",
                "creator" : {
                    "name": "Splash",
                    "version": splash.__version__,
                },
                "browser": {
                    "name": "QWebKit",
                    "version": unicode(qWebKitVersion()),
                    "comment": "PyQt %s, Qt %s" % (PYQT_VERSION_STR, QT_VERSION_STR),
                },
                "pages": [self.web_page.har_page_info],
                "entries": self.web_page.network_entries,
            }
        }
        return res

    # ======= Other helper methods:

    def _setViewportSize(self, viewport):
        w, h = map(int, viewport.split('x'))
        size = QSize(w, h)
        self.web_page.setViewportSize(size)

    def _setFullViewport(self):
        size = self.web_page.mainFrame().contentsSize()
        if size.isEmpty():
            self.log("contentsSize method doesn't work %s" % id(self.splash_request), min_level=1)
            self._setViewportSize(defaults.VIEWPORT_FALLBACK)
        else:
            self.web_page.setViewportSize(size)
        self.web_page.logEvent("_onFullViewportSet")

    def _loadJsLibs(self, frame, js_profile):
        if js_profile:
            for jsfile in os.listdir(js_profile):
                if jsfile.endswith('.js'):
                    with open(os.path.join(js_profile, jsfile)) as f:
                        frame.evaluateJavaScript(f.read().decode('utf-8'))

    def _runJS(self, js_source, js_profile):
        js_output = None
        js_console_output = None
        if js_source:
            frame = self.web_page.mainFrame()
            if self.console:
                js_console = JavascriptConsole()
                frame.addToJavaScriptWindowObject('console', js_console)
            if js_profile:
                self._loadJsLibs(frame, js_profile)
            ret = frame.evaluateJavaScript(js_source)
            js_output = bytes(ret.toString().toUtf8())
            if self.console:
                js_console_output = [bytes(s.toUtf8()) for s in js_console.messages]

        self.web_page.logEvent('_onCustomJsExecuted')
        return js_output, js_console_output

    def _frameToDict(self, frame, children=True, html=True):
        g = frame.geometry()
        res = {
            "url": unicode(frame.url().toString()),
            "requestedUrl": unicode(frame.requestedUrl().toString()),
            "geometry": (g.x(), g.y(), g.width(), g.height()),
            "title": unicode(frame.title())
        }
        if html:
            res["html"] = unicode(frame.toHtml())

        if children:
            res["childFrames"] = [self._frameToDict(f, True, html) for f in frame.childFrames()]
            res["frameName"] = unicode(frame.frameName())

        return res

    def _prepareRender(self):
        if self.viewport == 'full':
            self._setFullViewport()
        self.js_output, self.js_console_output = self._runJS(self.js_source, self.js_profile)

    def log(self, text, min_level=2):
        if self.verbosity >= min_level:
            if isinstance(text, unicode):
                text = text.encode('unicode-escape').decode('ascii')
            log.msg(text, system='render')


class HtmlRender(WebpageRender):
    def render(self):
        return self._getHtml()


class PngRender(WebpageRender):

    def doRequest(self, url, baseurl=None, wait_time=None, viewport=None,
                        js_source=None, js_profile=None, images=None,
                        width=None, height=None):
        self.width = width
        self.height = height
        super(PngRender, self).doRequest(
            url=url,
            baseurl=baseurl,
            wait_time=wait_time,
            viewport=viewport,
            js_source=js_source,
            js_profile=js_profile,
            images=images
        )

    def render(self):
        return self._getPng(self.width, self.height)


class JsonRender(WebpageRender):

    def doRequest(self, url, baseurl=None, wait_time=None, viewport=None,
                        js_source=None, js_profile=None, images=None,
                        html=True, iframes=True, png=True, script=True, console=False,
                        width=None, height=None, history=None, har=None):
        self.width = width
        self.height = height
        self.include = {'html': html, 'png': png, 'iframes': iframes,
                        'script': script, 'console': console,
                        'history': history, 'har': har}
        super(JsonRender, self).doRequest(
            url=url,
            baseurl=baseurl,
            wait_time=wait_time,
            viewport=viewport,
            js_source=js_source,
            js_profile=js_profile,
            images=images,
            console=console
        )

    def render(self):
        res = {}

        if self.include['png']:
            res['png'] = self._getPng(self.width, self.height, b64=True)

        if self.include['script'] and self.js_output:
            res['script'] = self.js_output

        if self.include['console'] and self.js_console_output:
            res['console'] = self.js_console_output

        res.update(self._getIframes(
            children=self.include['iframes'],
            html=self.include['html'],
        ))

        if self.include['history']:
            res['history'] = self._getHistory()

        if self.include['har']:
            res['har'] = self._getHAR()

        return json.dumps(res)


class HarRender(WebpageRender):
    def render(self):
        return json.dumps(self._getHAR())


class JavascriptConsole(QObject):
    def __init__(self, parent=None):
        self.messages = []
        super(JavascriptConsole, self).__init__(parent)

    @pyqtSlot(str)
    def log(self, message):
        self.messages.append(message)

import os, json, base64
from PyQt4.QtWebKit import QWebPage, QWebSettings, QWebView
from PyQt4.QtCore import Qt, QUrl, QBuffer, QSize, QTimer, QObject, pyqtSlot
from PyQt4.QtGui import QPainter, QImage
from PyQt4.QtNetwork import QNetworkRequest, QNetworkAccessManager
from twisted.internet import defer
from twisted.python import log
from splash import defaults


class RenderError(Exception):
    pass


class SplashQWebPage(QWebPage):

    def __init__(self, verbosity=0):
        super(QWebPage, self).__init__()
        self.verbosity = verbosity

    def javaScriptAlert(self, frame, msg):
        return

    def javaScriptConfirm(self, frame, msg):
        return False

    def javaScriptConsoleMessage(self, msg, line_number, source_id):
        if self.verbosity >= 2:
            log.msg("JsConsole(%s:%d): %s" % (source_id, line_number, msg), system='render')


class WebpageRender(object):

    def __init__(self, network_manager, splash_proxy_factory, splash_request, verbosity):
        self.network_manager = network_manager
        self.web_view = QWebView()
        self.web_page = SplashQWebPage(verbosity)
        self.web_page.setNetworkAccessManager(self.network_manager)
        self.web_view.setPage(self.web_page)
        self.web_view.setAttribute(Qt.WA_DeleteOnClose, True)
        settings = self.web_view.settings()
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


    def doRequest(self, url, baseurl=None, wait_time=None, viewport=None, js_source=None, js_profile=None, console=False):
        self.url = url
        self.wait_time = defaults.WAIT_TIME if wait_time is None else wait_time
        self.js_source = js_source
        self.js_profile = js_profile
        self.console = console
        self.viewport = defaults.VIEWPORT if viewport is None else viewport

        # setup logging
        if self.verbosity >= 4:
            self.web_page.loadStarted.connect(self._loadStarted)
            self.web_page.mainFrame().loadFinished.connect(self._frameLoadFinished)
            self.web_page.mainFrame().loadStarted.connect(self._frameLoadStarted)
            self.web_page.mainFrame().contentsSizeChanged.connect(self._contentsSizeChanged)

        if self.verbosity >= 3:
            self.web_page.mainFrame().javaScriptWindowObjectCleared.connect(self._javaScriptWindowObjectCleared)
            self.web_page.mainFrame().initialLayoutCompleted.connect(self._initialLayoutCompleted)

        # do the request
        request = QNetworkRequest()
        request.setUrl(QUrl(url))

        if self.viewport != 'full':
            # viewport='full' can't be set if content is not loaded yet
            self._setViewportSize(self.viewport)

        if baseurl:
            self._baseUrl = QUrl(baseurl)
            request.setOriginatingObject(self.web_page.mainFrame())
            self._reply = self.network_manager.get(request)
            self._reply.finished.connect(self._requestFinished)
        else:
            self.web_page.loadFinished.connect(self._loadFinished)

            if self.splash_request.method == 'POST':
                headers = self.splash_request.getAllHeaders()
                for header_name, header_value in headers.items():
                    request.setRawHeader(header_name, header_value)
                self.web_page.mainFrame().load(request,
                                               QNetworkAccessManager.PostOperation,
                                               self.splash_request.content.getvalue())
            else:
                self.web_page.mainFrame().load(request)

    def close(self):
        self.web_view.stop()
        self.web_view.close()
        self.web_page.deleteLater()
        self.web_view.deleteLater()

    def _requestFinished(self):
        self.log("_requestFinished %s" % id(self.splash_request))
        self.web_view.loadFinished.connect(self._loadFinished)
        mimeType = self._reply.header(QNetworkRequest.ContentTypeHeader).toString()
        data = self._reply.readAll()
        self.web_view.page().mainFrame().setContent(data, mimeType, self._baseUrl)
        if self._reply.error():
            self.log("Error loading %s: %s" % (self.url, self._reply.errorString()), min_level=1)
        self._reply.close()
        self._reply.deleteLater()

    def _loadFinished(self, ok):
        if self.deferred.called:
            # sometimes this callback is called multiple times
            self.log("loadFinished called multiple times", min_level=1)
            return
        if ok:
            time_ms = int(self.wait_time * 1000)
            self.log("loadFinished %s; waiting %sms" % (id(self.splash_request), time_ms))
            QTimer.singleShot(time_ms, self._loadFinishedOK)
        else:
            self.log("loadFinished %s: error" % id(self.splash_request), min_level=1)
            self.deferred.errback(RenderError())

    def _loadFinishedOK(self):
        self.log("_loadFinishedOK %s" % id(self.splash_request))
        try:
            self._prerender()
            self.deferred.callback(self._render())
        except:
            self.deferred.errback()

    def _frameLoadFinished(self, ok):
        self.log("mainFrame().LoadFinished %s %s" % (id(self.splash_request), ok), min_level=4)

    def _loadStarted(self):
        self.log("loadStarted %s" % id(self.splash_request), min_level=4)

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

        frame = self.web_view.page().mainFrame()
        return bytes(frame.toHtml().toUtf8())

    def _getPng(self, width=None, height=None):
        self.log("getting PNG %s" % id(self.splash_request))

        image = QImage(self.web_page.viewportSize(), QImage.Format_ARGB32)
        painter = QPainter(image)
        self.web_page.mainFrame().render(painter)
        painter.end()
        if width:
            image = image.scaledToWidth(width, Qt.SmoothTransformation)
        if height:
            image = image.copy(0, 0, width, height)
        b = QBuffer()
        image.save(b, "png")
        return bytes(b.data())

    def _getIframes(self, children=True, html=True):
        self.log("getting iframes %s" % id(self.splash_request))
        frame = self.web_view.page().mainFrame()
        return self._frameToDict(frame, children, html)

    def _render(self):
        raise NotImplementedError()

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
            frame = self.web_view.page().mainFrame()
            if self.console:
                js_console = JavascriptConsole()
                frame.addToJavaScriptWindowObject('console', js_console)
            if js_profile:
                self._loadJsLibs(frame, js_profile)
            ret = frame.evaluateJavaScript(js_source)
            js_output = bytes(ret.toString().toUtf8())
            if self.console:
                js_console_output = [bytes(s.toUtf8()) for s in js_console.messages]
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

    def _prerender(self):
        if self.viewport == 'full':
            self._setFullViewport()
        self.js_output, self.js_console_output = self._runJS(self.js_source, self.js_profile)

    def log(self, text, min_level=2):
        if self.verbosity >= min_level:
            if isinstance(text, unicode):
                text = text.encode('unicode-escape').decode('ascii')
            log.msg(text, system='render')


class HtmlRender(WebpageRender):
    def _render(self):
        return self._getHtml()


class PngRender(WebpageRender):

    def doRequest(self, url, baseurl=None, wait_time=None, viewport=None, js_source=None, js_profile=None,
                        width=None, height=None):
        self.width = width
        self.height = height
        super(PngRender, self).doRequest(url, baseurl, wait_time, viewport, js_source, js_profile)

    def _render(self):
        return self._getPng(self.width, self.height)


class JsonRender(WebpageRender):

    def doRequest(self, url, baseurl=None, wait_time=None, viewport=None, js_source=None, js_profile=None,
                        html=True, iframes=True, png=True, script=True, console=False,
                        width=None, height=None):
        self.width = width
        self.height = height
        self.include = {'html': html, 'png': png, 'iframes': iframes,
                        'script': script, 'console': console}
        super(JsonRender, self).doRequest(url, baseurl, wait_time, viewport, js_source, js_profile, console)

    def _render(self):
        res = {}

        if self.include['png']:
            png = self._getPng(self.width, self.height)
            res['png'] = base64.encodestring(png)

        if self.include['script'] and self.js_output:
            res['script'] = self.js_output
        if self.include['console'] and self.js_console_output:
            res['console'] = self.js_console_output

        res.update(self._getIframes(
            children=self.include['iframes'],
            html=self.include['html'],
        ))
        return json.dumps(res)


class JavascriptConsole(QObject):
    def __init__(self, parent=None):
        self.messages = []
        super(JavascriptConsole, self).__init__(parent)

    @pyqtSlot(str)
    def log(self, message):
        self.messages.append(message)

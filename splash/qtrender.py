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

    def javaScriptAlert(self, frame, msg):
        return

    def javaScriptConfirm(self, frame, msg):
        return False


class WebpageRender(object):

    def __init__(self, network_manager, splash_proxy_factory, splash_request, verbose=False):
        self.network_manager = network_manager
        self.web_view = QWebView()
        self.web_page = SplashQWebPage()
        self.web_page.setNetworkAccessManager(self.network_manager)
        self.web_view.setPage(self.web_page)
        self.web_view.setAttribute(Qt.WA_DeleteOnClose, True)
        settings = self.web_view.settings()
        settings.setAttribute(QWebSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebSettings.PluginsEnabled, False)
        settings.setAttribute(QWebSettings.PrivateBrowsingEnabled, True)
        settings.setAttribute(QWebSettings.LocalStorageEnabled, True)
        self.web_page.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        self.web_page.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)

        self.splash_request = splash_request
        self.web_page.splash_request = splash_request
        self.web_page.splash_proxy_factory = splash_proxy_factory
        self.verbose = verbose

    # ======= General request/response handling:


    def doRequest(self, url, baseurl=None, wait_time=None, viewport=None, js_source=None, js_profile=None, console=False):
        self.url = url
        self.wait_time = defaults.WAIT_TIME if wait_time is None else wait_time
        self.js_source = js_source
        self.js_profile = js_profile
        self.console = console
        self.viewport = defaults.VIEWPORT if viewport is None else viewport

        self.deferred = defer.Deferred()
        request = QNetworkRequest()
        request.setUrl(QUrl(url))

        if self.viewport != 'full':
            # viewport='full' can't be set if content is not loaded yet
            self._setViewportSize(self.viewport)

        self.web_page.loadStarted.connect(self._loadStarted)
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
            log.msg("Error loading %s: %s" % (self.url, self._reply.errorString()), system='render')
        self._reply.close()
        self._reply.deleteLater()

    def _loadStarted(self):
        self.log("_loadStarted %s" % id(self.splash_request))
        self.web_page.loading = True

    def _loadFinished(self, ok):
        self.log("_loadFinished %s ok:%s" % (id(self.splash_request), ok))
        self.web_page.loading = False
        if ok:
            time_ms = int(self.wait_time * 1000)
            QTimer.singleShot(time_ms, self._loadFinishedOK)
        else:
            QTimer.singleShot(defaults.LOAD_FINISHED_DELAY, self._isReallyFinished)

    def _loadFinishedOK(self):
        self.log("_loadFinishedOK %s" % id(self.splash_request))
        try:
            self._prerender()
            self.deferred.callback(self._render())
        except:
            self.deferred.errback()

    def _isReallyFinished(self):
        self.log("_isReallyFinished %s" % id(self.splash_request))
        if not self.web_page.loading:
            self.deferred.errback(RenderError())

    # ======= Rendering methods that subclasses can use:

    def _getHtml(self):
        frame = self.web_view.page().mainFrame()
        return bytes(frame.toHtml().toUtf8())

    def _getPng(self, width=None, height=None):
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
            self.log("contentsSize method doesn't work %s" % id(self.splash_request))
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

    def log(self, text):
        if self.verbose:
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

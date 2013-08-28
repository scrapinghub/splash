import json, base64
from PyQt4.QtWebKit import QWebPage, QWebSettings, QWebView
from PyQt4.QtCore import Qt, QUrl, QBuffer, QSize, QTimer
from PyQt4.QtCore import QObject, pyqtSlot
from PyQt4.QtGui import QPainter, QImage
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest
from twisted.internet import defer
from twisted.python import log
from splash import defaults


class RenderError(Exception):
    pass


class SplashQNetworkAccessManager(QNetworkAccessManager):

    def __init__(self, *args, **kwargs):
        super(SplashQNetworkAccessManager, self).__init__(*args, **kwargs)
        self.sslErrors.connect(self._sslErrors)
        self.finished.connect(self._finished)

    def _sslErrors(self, reply, errors):
        reply.ignoreSslErrors()

    def _finished(self, reply):
        reply.deleteLater()


class SplashQWebPage(QWebPage):

    def javaScriptAlert(self, frame, msg):
        return

    def javaScriptConfirm(self, frame, msg):
        return False


class WebpageRender(object):

    def __init__(self, cache=None, proxy_factory=None):
        self.network_manager = SplashQNetworkAccessManager()

        if cache:
            self.network_manager.setCache(cache)

        if proxy_factory:
            self.network_manager.setProxyFactory(proxy_factory)

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

    def doRequest(self, url, baseurl=None, wait_time=None):
        self.url = url
        self.wait_time = defaults.WAIT_TIME if wait_time is None else wait_time

        self.deferred = defer.Deferred()
        request = QNetworkRequest()
        request.setUrl(QUrl(url))
        if baseurl:
            self._baseUrl = QUrl(baseurl)
            self.network_manager.finished.connect(self._requestFinished)
            self.network_manager.get(request)
        else:
            self.web_page.loadFinished.connect(self._loadFinished)
            self.web_page.mainFrame().load(request)

    def close(self):
        self.web_view.stop()
        self.web_view.close()
        self.web_page.deleteLater()
        self.web_view.deleteLater()
        self.network_manager.deleteLater()

    def _requestFinished(self, reply):
        self.web_page.networkAccessManager().finished.disconnect(self._requestFinished)
        self.web_view.loadFinished.connect(self._loadFinished)
        mimeType = reply.header(QNetworkRequest.ContentTypeHeader).toString()
        self.web_view.page().mainFrame().setContent(reply.readAll(), mimeType, self._baseUrl)

    def _loadFinished(self, ok):
        if self.deferred.called:
            return
        if ok:
            time_ms = int(self.wait_time * 1000)
            QTimer.singleShot(time_ms, self._loadFinishedOK)
        else:
            self.deferred.errback(RenderError())

    def _loadFinishedOK(self):
        if self.deferred.called:
            return
        try:
            self.deferred.callback(self._render())
        except:
            self.deferred.errback()


    def _getHtml(self):
        frame = self.web_view.page().mainFrame()
        return bytes(frame.toHtml().toUtf8())

    def _getPng(self, width=None, height=None, viewport=None):
        self._setViewportSize(viewport)
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


    def _setViewportSize(self, viewport=None):
        viewport = defaults.VIEWPORT if viewport is None else viewport

        if viewport == 'full':
            size = self.web_page.mainFrame().contentsSize()
            if size.isEmpty():  # sometimes contentsSize doesn't work
                w, h = map(int, defaults.VIEWPORT_FALLBACK.split('x'))
                size = QSize(w, h)
        else:
            w, h = map(int, viewport.split('x'))
            size = QSize(w, h)

        self.web_page.setViewportSize(size)

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

    def _render(self):
        raise NotImplementedError()


class HtmlRender(WebpageRender):
    def _render(self):
        return self._getHtml()


class PngRender(WebpageRender):

    def doRequest(self, url, baseurl=None, wait_time=None, width=None, height=None, viewport=None):
        self.width = width
        self.height = height
        self.viewport = viewport
        super(PngRender, self).doRequest(url, baseurl, wait_time)

    def _render(self):
        return self._getPng(self.width, self.height, self.viewport)


class JsonRender(WebpageRender):

    def doRequest(self, url, baseurl=None, wait_time=None,
                        html=True, iframes=True, png=True,
                        width=None, height=None, viewport=None):
        self.width = width
        self.height = height
        self.viewport = viewport
        self.include = {'html': html, 'png': png, 'iframes': iframes}
        super(JsonRender, self).doRequest(url, baseurl, wait_time)

    def _render(self):
        res = {}

        if self.include['png']:
            png = self._getPng(self.width, self.height, self.viewport)
            res['png'] = base64.encodestring(png)

        res.update(self._getIframes(
            children=self.include['iframes'],
            html=self.include['html'],
        ))
        return json.dumps(res)


class JsRender(WebpageRender):

    def doRequest(self, url, baseurl=None, wait_time=None,
                        js=None):
        self.js = js
        super(JsRender, self).doRequest(url, baseurl, wait_time)

    def _render(self):
        printer = ConsolePrinter()
        frame = self.web_view.page().mainFrame()
        frame.addToJavaScriptWindowObject('printer', printer)
        ret = frame.evaluateJavaScript(self.js)
        return bytes(ret.toString().toUtf8())


class ConsolePrinter(QObject):
    def __init__(self, parent=None):
        super(ConsolePrinter, self).__init__(parent)

    @pyqtSlot(str)
    def text(self, message):
        log.msg(message)

import json, os
from PyQt4.QtWebKit import QWebPage, QWebSettings, QWebView
from PyQt4.QtCore import Qt, QUrl, QBuffer, QSize
from PyQt4.QtGui import QPainter, QImage
from PyQt4.QtNetwork import (QNetworkAccessManager, QNetworkRequest,
                             QNetworkDiskCache)
from twisted.internet import defer

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


class HtmlRender(object):

    def __init__(self, url, baseurl=None):
        self.url = url
        self.web_view = QWebView()
        self.network_manager = SplashQNetworkAccessManager()

        if os.environ.get('SPLASH_CACHE_PATH'):
            cache = QNetworkDiskCache()
            cache.setCacheDirectory(os.environ['SPLASH_CACHE_PATH'])
            cache.setMaximumCacheSize(os.environ.get('SPLASH_CACHE_SIZE', 50*1024*1024))
            self.network_manager.setCache(cache)

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
            try:
                self.deferred.callback(self._render())
            except:
                self.deferred.errback()
        else:
            self.deferred.errback(RenderError())

    def _render(self):
        frame = self.web_view.page().mainFrame()
        return str(frame.toHtml().toUtf8())


class PngRender(HtmlRender):

    def __init__(self, url, baseurl=None, width=None, height=None, vwidth=1024, vheight=768):
        HtmlRender.__init__(self, url, baseurl)
        self.width = width
        self.height = height
        self.vwidth = vwidth
        self.vheight = vheight

    def _render(self):
        self.web_page.setViewportSize(QSize(self.vwidth, self.vheight))
        image = QImage(self.web_page.viewportSize(), QImage.Format_ARGB32)
        painter = QPainter(image)
        self.web_page.mainFrame().render(painter)
        painter.end()
        if self.width:
            image = image.scaledToWidth(self.width, Qt.SmoothTransformation)
        if self.height:
            image = image.copy(0, 0, self.width, self.height)
        b = QBuffer()
        image.save(b, "png")
        return str(b.data())


class IframesRender(HtmlRender):

    def _render(self):
        frame = self.web_view.page().mainFrame()
        return json.dumps(self._frameToDict(frame))

    def _frameToDict(self, frame):
        g = frame.geometry()
        return {
            "url": str(frame.url().toString()),
            "requestedUrl": str(frame.requestedUrl().toString()),
            "html": unicode(frame.toHtml()),
            "name": unicode(frame.frameName()),
            "geometry": (g.x(), g.y(), g.width(), g.height()),
            "childFrames": map(self._frameToDict, frame.childFrames()),
        }

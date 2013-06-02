from PyQt4.QtWebKit import QWebPage, QWebSettings, QWebView
from PyQt4.QtCore import Qt, QUrl, QBuffer, QSize
from PyQt4.QtGui import QPainter, QImage
from PyQt4.QtNetwork import QNetworkRequest
from twisted.internet import defer

qWebSettings = {
    QWebSettings.JavascriptEnabled : True,
    QWebSettings.PluginsEnabled : False,
    QWebSettings.PrivateBrowsingEnabled : True,
    QWebSettings.LocalStorageEnabled : True,
    #QWebSettings.JavascriptCanOpenWindows : True,
    #QWebSettings.FrameFlatteningEnabled :  True,
    #QWebSettings.DeveloperExtrasEnabled :  True,
}


for key, value in qWebSettings.iteritems():
    QWebSettings.globalSettings().setAttribute(key, value)

class RenderError(Exception):
    pass


class HtmlRender(QWebPage):

    def __init__(self, url, baseurl=None):
        QWebPage.__init__(self)  
        self.webview = QWebView()
        self.webview.setPage(self)
        #self.webview.show()
  
        self.format = format
        self.deferred = defer.Deferred(self.cancel)
        if baseurl:
            self._baseUrl = QUrl(baseurl)
            request = QNetworkRequest()
            request.setUrl(QUrl(url))

            self.networkAccessManager().finished.connect(self._urlFinished)
            self.networkAccessManager().get(request)
        else:
            self.loadFinished.connect(self._loadFinished)
            self.mainFrame().load(QUrl(url))

    def _loadFinished(self, ok):
        if ok:
            try:
                self.deferred.callback(self._render())
            except:
                self.deferred.errback()
        else:
            self.deferred.errback(RenderError())

    def _render(self):
        return str(self.mainFrame().toHtml().toUtf8())

    def _urlFinished(self, reply):
        self.networkAccessManager().finished.disconnect(self._urlFinished)
        self.loadFinished.connect(self._loadFinished)
        mimeType = reply.header(QNetworkRequest.ContentTypeHeader).toString()
        self.mainFrame().setContent(reply.readAll(), mimeType, self._baseUrl)

    def cancel(self, _):
        self.loadFinished.disconnect(self._loadFinished)
        self.webview.stop()

    def javaScriptAlert(self, frame, msg):
        return

    def javaScriptConfirm(self, frame, msg):
        return False


class PngRender(HtmlRender):

    def __init__(self, url, baseurl=None, width=None, height=None, vwidth=1280, vheight=960):
        HtmlRender.__init__(self, url, baseurl)
        self.width = width
        self.height = height
        self.vwidth = vwidth
        self.vheight = vheight

    def _render(self):
        self.setViewportSize(QSize(self.vwidth, self.vheight))
        image = QImage(self.viewportSize(), QImage.Format_ARGB32)
        painter = QPainter(image)
        self.mainFrame().render(painter)
        painter.end()
        if self.width:
            image = image.scaledToWidth(self.width, Qt.SmoothTransformation)
        if self.height:
            image = image.copy(0, 0, self.width, self.height)
        b = QBuffer()
        image.save(b, "png")
        return str(b.data())

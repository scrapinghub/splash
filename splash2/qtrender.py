from PyQt4.QtWebKit import QWebPage, QWebSettings, QWebView
from PyQt4.QtCore import QUrl
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

class WebkitRender(QWebPage):  

    def __init__(self, url, baseurl=None):
        QWebPage.__init__(self)  
        self.webview = QWebView()
        self.webview.setPage(self)
        #self.webview.show()
  
        self.deferred = defer.Deferred()
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
            self.deferred.callback(str(self.mainFrame().toHtml().toUtf8()))
        else:
            self.deferred.errback(RenderError())

    def _urlFinished(self, reply):
        self.networkAccessManager().finished.disconnect(self._urlFinished)
        self.loadFinished.connect(self._loadFinished)
        mimeType = reply.header(QNetworkRequest.ContentTypeHeader).toString()
        self.mainFrame().setContent(reply.readAll(), mimeType, self._baseUrl)

    def cancel(self):
        self.webview.stop()

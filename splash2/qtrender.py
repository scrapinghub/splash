from PyQt4.QtWebKit import QWebPage, QWebSettings, QWebView
from PyQt4.QtCore import QUrl
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

    def __init__(self, url):
        QWebPage.__init__(self)  
        self.webview = QWebView()
        self.webview.setPage(self)
        #self.webview.show()
  
        d = defer.Deferred()
        d.addCallback(self._loadFinished)
        self.loadFinished.connect(d.callback)
        self.mainFrame().load(QUrl(url))  
        self.deferred = d

    def _loadFinished(self, ok):
        if ok:
            return str(self.mainFrame().toHtml().toUtf8())
        raise RenderError()

    def cancel(self):
        self.webview.stop()

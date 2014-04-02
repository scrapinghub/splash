from twisted.web import http
from twisted.web import server


class SplashRequest(server.Request):

    def __init__(self, channel, queued):
        http.Request.__init__(self, channel, queued)
        self.proxy_mode = False


class SplashSite(server.Site):
    requestFactory = SplashRequest


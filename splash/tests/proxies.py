# -*- coding: utf-8 -*-
import base64
from twisted.web import proxy, http


class ProxyClient(proxy.ProxyClient):
    def handleResponsePart(self, buffer):
        buffer = buffer.replace(b'</body>', b' PROXY_USED</body>')
        proxy.ProxyClient.handleResponsePart(self, buffer)


class ProxyClientFactory(proxy.ProxyClientFactory):
    protocol = ProxyClient


class ProxyRequest(proxy.ProxyRequest):
    protocols = {b'http': ProxyClientFactory}


class Proxy(proxy.Proxy):
    requestFactory = ProxyRequest


class ProxyFactory(http.HTTPFactory):
    protocol = Proxy


class AuthProxyRequest(proxy.ProxyRequest):
    protocols = {b'http': ProxyClientFactory}
    valid_password = b"splash"

    def process(self):
        headers = self.getAllHeaders()
        auth = headers.get(b'proxy-authorization')
        valid_user = self.transport.protocol.factory.valid_user.encode("utf-8")

        if not auth:
            self.reject_request()
            return
        _, auth_string = auth.split()
        user, password = base64.b64decode(auth_string).split(b":", 1)

        if user != valid_user or password != self.valid_password:
            self.reject_request()
            return

        # can't use super() because old style classes
        proxy.ProxyRequest.process(self)

    def reject_request(self):
        self.setResponseCode(407)
        self.setHeader(b"Proxy-Authenticate", b"Basic realm: 'mockserver'")
        self.finish()


class AuthProxy(proxy.Proxy):
    requestFactory = AuthProxyRequest


class AuthProxyFactory(http.HTTPFactory):
    protocol = AuthProxy

    def __init__(self, user):
        http.HTTPFactory.__init__(self)
        self.valid_user = user

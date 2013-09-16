# -*- coding: utf-8 -*-
from __future__ import absolute_import
import re
from PyQt4.QtCore import QUrl
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkProxyQuery
from PyQt4.QtWebKit import QWebFrame
from splash.utils import getarg


class SplashQNetworkAccessManager(QNetworkAccessManager):
    """
    This QNetworkAccessManager subclass enables "splash proxy factories"
    support. Qt provides similar functionality via setProxyFactory method,
    but standard QNetworkProxyFactory is not flexible enough.
    """

    def __init__(self):
        super(SplashQNetworkAccessManager, self).__init__()
        self.sslErrors.connect(self._sslErrors)
        self.finished.connect(self._finished)

        assert self.proxyFactory() is None, "Standard QNetworkProxyFactory is not supported"

    def _sslErrors(self, reply, errors):
        reply.ignoreSslErrors()

    def _finished(self, reply):
        reply.deleteLater()

    def createRequest(self, operation, request, outgoingData=None):
        old_proxy = self.proxy()

        splash_proxy_factory = self._getSplashProxyFactory(request)
        if splash_proxy_factory:
            proxy_query = QNetworkProxyQuery(request.url())
            proxy = splash_proxy_factory.queryProxy(proxy_query)[0]
            self.setProxy(proxy)

        # this method is called createRequest, but in fact it creates a reply
        reply = super(SplashQNetworkAccessManager, self).createRequest(
            operation, request, outgoingData
        )

        self.setProxy(old_proxy)
        return reply

    def _getSplashRequest(self, request):
        return self._getWebPageAttribute(request, 'splash_request')

    def _getSplashProxyFactory(self, request):
        return self._getWebPageAttribute(request, 'splash_proxy_factory')

    def _getWebPageAttribute(self, request, attribute):
        web_frame = request.originatingObject()
        if isinstance(web_frame, QWebFrame):
            return getattr(web_frame.page(), attribute, None)

    def _drop_request(self, request):
        # hack: set invalid URL
        request.setUrl(QUrl('forbidden://localhost/'))


class FilteringQNetworkAccessManager(SplashQNetworkAccessManager):
    """
    This SplashQNetworkAccessManager subclass enables request filtering
    based on 'allowed_domains' GET parameter in original Splash request.
    """
    def __init__(self, allow_subdomains=True):
        self.allow_subdomains = allow_subdomains
        super(FilteringQNetworkAccessManager, self).__init__()

    def createRequest(self, operation, request, outgoingData=None):
        splash_request = self._getSplashRequest(request)
        if splash_request:
            allowed_domains = self._get_allowed_domains(splash_request)
            host_re = self._get_host_regex(allowed_domains, self.allow_subdomains)
            if not host_re.match(unicode(request.url().host())):
                self._drop_request(request)

        return super(FilteringQNetworkAccessManager, self).createRequest(operation, request, outgoingData)

    def _get_allowed_domains(self, splash_request):
        allowed_domains = getarg(splash_request, "allowed_domains", None)
        if allowed_domains is not None:
            return allowed_domains.split(',')

    def _get_host_regex(self, allowed_domains, allow_subdomains):
        """Override this method to implement a different offsite policy"""
        if not allowed_domains:
            return re.compile('')  # allow all by default
        domains = [d.replace('.', r'\.') for d in allowed_domains]
        if allow_subdomains:
            regex = r'(.*\.)?(%s)$' % '|'.join(domains)
        else:
            regex = r'(%s)$' % '|'.join(domains)
        return re.compile(regex, re.IGNORECASE)

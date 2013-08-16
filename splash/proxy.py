# -*- coding: utf-8 -*-
from __future__ import absolute_import
import re
from PyQt4.QtNetwork import QNetworkProxyFactory, QNetworkProxy


class SplashQNetworkProxyFactory(QNetworkProxyFactory):
    """
    Proxy factory that enables non-default proxy list when
    requested URL is matched by one of whitelist patterns
    while not being matched by one of the blacklist patterns.
    """
    def __init__(self, blacklist=None, whitelist=None, proxy_list=None):
        self.blacklist = blacklist or []
        self.whitelist = whitelist or []
        self.proxy_list = proxy_list or []
        super(SplashQNetworkProxyFactory, self).__init__()

    def queryProxy(self, query=None, *args, **kwargs):
        if self.shouldUseDefault(query.protocolTag(), unicode(query.url())):
            return self._defaultProxyList()
        return self._customProxyList()

    def shouldUseDefault(self, protocol, url):
        if not self.proxy_list:
            return True

        if protocol != 'http':  # don't try to proxy https
            return True

        if any(re.match(p, url) for p in self.blacklist):
            return True

        if any(re.match(p, url) for p in self.whitelist):
            return False

        return bool(self.whitelist)

    def _defaultProxyList(self):
        return [QNetworkProxy(QNetworkProxy.DefaultProxy)]

    def _customProxyList(self):
        return [
            QNetworkProxy(QNetworkProxy.HttpProxy, *args)
            for args in self.proxy_list
        ]

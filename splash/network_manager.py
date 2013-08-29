# -*- coding: utf-8 -*-
from __future__ import absolute_import
import re
from PyQt4.QtCore import QUrl
from PyQt4.QtNetwork import QNetworkAccessManager
from splash.utils import getarg

class SplashQNetworkAccessManager(QNetworkAccessManager):
    def __init__(self, *args, **kwargs):
        super(SplashQNetworkAccessManager, self).__init__(*args, **kwargs)
        self.sslErrors.connect(self._sslErrors)
        self.finished.connect(self._finished)

    def _sslErrors(self, reply, errors):
        reply.ignoreSslErrors()

    def _finished(self, reply):
        reply.deleteLater()


class FilteringQNetworkAccessManager(SplashQNetworkAccessManager):

    def __init__(self, request, allow_subdomains=True):
        allowed_domains = getarg(request, "allowed_domains", None)
        if allowed_domains is not None:
            allowed_domains = allowed_domains.split(',')
        self.host_re = self.get_host_regex(allowed_domains, allow_subdomains)
        super(FilteringQNetworkAccessManager, self).__init__()

    def createRequest(self, QNetworkAccessManager_Operation, QNetworkRequest, QIODevice_device=None):
        if not self.host_re.match(unicode(QNetworkRequest.url().host())):
            # hack: set invalid URL
            QNetworkRequest.setUrl(QUrl('forbidden://localhost/'))

        # this method is called crateRequest, but in fact it creates a reply
        reply = super(FilteringQNetworkAccessManager, self).createRequest(
            QNetworkAccessManager_Operation, QNetworkRequest, QIODevice_device)
        return reply

    def get_host_regex(self, allowed_domains, allow_subdomains):
        """Override this method to implement a different offsite policy"""
        if not allowed_domains:
            return re.compile('')  # allow all by default
        domains = [d.replace('.', r'\.') for d in allowed_domains]
        if allow_subdomains:
            regex = r'(.*\.)?(%s)$' % '|'.join(domains)
        else:
            regex = r'(%s)$' % '|'.join(domains)
        return re.compile(regex, re.IGNORECASE)

# -*- coding: utf-8 -*-
from __future__ import absolute_import
import re
from PyQt4.QtCore import QUrl
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkProxyQuery, QNetworkReply
from PyQt4.QtWebKit import QWebFrame
from splash.utils import getarg
from twisted.python import log


# See: http://pyqt.sourceforge.net/Docs/PyQt4/qnetworkreply.html#NetworkError-enum
REQUEST_ERRORS = {
    QNetworkReply.NoError : 'no error condition. Note: When the HTTP protocol returns a redirect no error will be reported. You can check if there is a redirect with the QNetworkRequest::RedirectionTargetAttribute attribute.',
    QNetworkReply.ConnectionRefusedError : 'the remote server refused the connection (the server is not accepting requests)',
    QNetworkReply.RemoteHostClosedError : 'the remote server closed the connection prematurely, before the entire reply was received and processed',
    QNetworkReply.HostNotFoundError : 'the remote host name was not found (invalid hostname)',
    QNetworkReply.TimeoutError : 'the connection to the remote server timed out',
    QNetworkReply.OperationCanceledError : 'the operation was canceled via calls to abort() or close() before it was finished.',
    QNetworkReply.SslHandshakeFailedError : 'the SSL/TLS handshake failed and the encrypted channel could not be established. The sslErrors() signal should have been emitted.',
    QNetworkReply.ProxyConnectionRefusedError : 'the connection to the proxy server was refused (the proxy server is not accepting requests)',
    QNetworkReply.ProxyConnectionClosedError : 'the proxy server closed the connection prematurely, before the entire reply was received and processed',
    QNetworkReply.ProxyNotFoundError : 'the proxy host name was not found (invalid proxy hostname)',
    QNetworkReply.ProxyTimeoutError : 'the connection to the proxy timed out or the proxy did not reply in time to the request sent',
    QNetworkReply.ProxyAuthenticationRequiredError : 'the proxy requires authentication in order to honour the request but did not accept any credentials offered (if any)',
    QNetworkReply.ContentAccessDenied : 'the access to the remote content was denied (similar to HTTP error 401)',
    QNetworkReply.ContentOperationNotPermittedError : 'the operation requested on the remote content is not permitted',
    QNetworkReply.ContentNotFoundError : 'the remote content was not found at the server (similar to HTTP error 404)',
    QNetworkReply.AuthenticationRequiredError : 'the remote server requires authentication to serve the content but the credentials provided were not accepted (if any)',
    QNetworkReply.ProtocolUnknownError : 'the Network Access API cannot honor the request because the protocol is not known',
    QNetworkReply.ProtocolInvalidOperationError : 'the requested operation is invalid for this protocol',
    QNetworkReply.UnknownNetworkError : 'an unknown network-related error was detected',
    QNetworkReply.UnknownProxyError : 'an unknown proxy-related error was detected',
    QNetworkReply.UnknownContentError : 'an unknown error related to the remote content was detected',
    QNetworkReply.ProtocolFailure : 'a breakdown in protocol was detected (parsing error, invalid or unexpected responses, etc.)',
}

# Errors that are only present in PyQt4 2.7 and above
NEW_REQUEST_ERRORS = {
    'TemporaryNetworkFailureError': 'the connection was broken due to disconnection from the network, however the system has initiated roaming to another access point. The request should be resubmitted and will be processed as soon as the connection is re-established.',
    'ContentReSendError': 'the request needed to be sent again, but this failed for example because the upload data could not be read a second time.',
}

# Only add new error types if supported
for attr, value in NEW_REQUEST_ERRORS.items():
    attr = getattr(QNetworkReply, attr, None)
    if attr is not None:
        REQUEST_ERRORS[attr] = value


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

        reply.error.connect(self._handle_error)
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

    def _handle_error(self, error_id):
        url = self.sender().url().toString()
        error_msg = REQUEST_ERRORS.get(error_id, 'unknown error')
        log.msg("Error %d: %s (%s)" % (error_id, error_msg, url), system='network')


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

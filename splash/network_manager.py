# -*- coding: utf-8 -*-
from __future__ import absolute_import
import datetime
from functools import partial

from PyQt4.QtNetwork import (
    QNetworkAccessManager, QNetworkProxyQuery,
    QNetworkReply, QNetworkRequest
)
from PyQt4.QtWebKit import QWebFrame
from twisted.python import log

from splash.qtutils import qurl2ascii
from splash import har
from splash.request_middleware import (
    AdblockMiddleware,
    AllowedDomainsMiddleware,
    AllowedSchemesMiddleware,
    RequestLoggingMiddleware,
    AdblockRulesRegistry,
)


# See: http://pyqt.sourceforge.net/Docs/PyQt4/qnetworkreply.html#NetworkError-enum
REQUEST_ERRORS = {
    QNetworkReply.NoError : 'no error condition. Note: When the HTTP protocol returns a redirect no error will be reported. You can check if there is a redirect with the QNetworkRequest::RedirectionTargetAttribute attribute.',
    QNetworkReply.ConnectionRefusedError : 'the remote server refused the connection (the server is not accepting requests)',
    QNetworkReply.RemoteHostClosedError : 'the remote server closed the connection prematurely, before the entire reply was received and processed',
    QNetworkReply.HostNotFoundError : 'the remote host name was not found (invalid hostname)',
    QNetworkReply.TimeoutError : 'the connection to the remote server timed out',
    QNetworkReply.OperationCanceledError : 'the operation was canceled via calls to abort() or close() before it was finished.',
    QNetworkReply.SslHandshakeFailedError : 'the SSL/TLS handshake failed and the encrypted channel could not be established. The sslErrors() signal should have been emitted.',
    QNetworkReply.TemporaryNetworkFailureError : 'the connection was broken due to disconnection from the network, however the system has initiated roaming to another access point. The request should be resubmitted and will be processed as soon as the connection is re-established.',
    QNetworkReply.ProxyConnectionRefusedError : 'the connection to the proxy server was refused (the proxy server is not accepting requests)',
    QNetworkReply.ProxyConnectionClosedError : 'the proxy server closed the connection prematurely, before the entire reply was received and processed',
    QNetworkReply.ProxyNotFoundError : 'the proxy host name was not found (invalid proxy hostname)',
    QNetworkReply.ProxyTimeoutError : 'the connection to the proxy timed out or the proxy did not reply in time to the request sent',
    QNetworkReply.ProxyAuthenticationRequiredError : 'the proxy requires authentication in order to honour the request but did not accept any credentials offered (if any)',
    QNetworkReply.ContentAccessDenied : 'the access to the remote content was denied (similar to HTTP error 401)',
    QNetworkReply.ContentOperationNotPermittedError : 'the operation requested on the remote content is not permitted',
    QNetworkReply.ContentNotFoundError : 'the remote content was not found at the server (similar to HTTP error 404)',
    QNetworkReply.AuthenticationRequiredError : 'the remote server requires authentication to serve the content but the credentials provided were not accepted (if any)',
    QNetworkReply.ContentReSendError : 'the request needed to be sent again, but this failed for example because the upload data could not be read a second time.',
    QNetworkReply.ProtocolUnknownError : 'the Network Access API cannot honor the request because the protocol is not known',
    QNetworkReply.ProtocolInvalidOperationError : 'the requested operation is invalid for this protocol',
    QNetworkReply.UnknownNetworkError : 'an unknown network-related error was detected',
    QNetworkReply.UnknownProxyError : 'an unknown proxy-related error was detected',
    QNetworkReply.UnknownContentError : 'an unknown error related to the remote content was detected',
    QNetworkReply.ProtocolFailure : 'a breakdown in protocol was detected (parsing error, invalid or unexpected responses, etc.)',
}


class ProxiedQNetworkAccessManager(QNetworkAccessManager):
    """
    This QNetworkAccessManager subclass enables "splash proxy factories"
    support. Qt provides similar functionality via setProxyFactory method,
    but standard QNetworkProxyFactory is not flexible enough.

    It also sets up some extra logging and provides a way to get
    the "source" request (that was made to Splash itself).
    """
    def __init__(self, verbosity):
        super(ProxiedQNetworkAccessManager, self).__init__()
        self.sslErrors.connect(self._sslErrors)
        self.finished.connect(self._finished)
        self.verbosity = verbosity

        assert self.proxyFactory() is None, "Standard QNetworkProxyFactory is not supported"

    def _sslErrors(self, reply, errors):
        reply.ignoreSslErrors()

    def _finished(self, reply):
        reply.deleteLater()

    def createRequest(self, operation, request, outgoingData=None):
        start_time = datetime.datetime.utcnow()

        request = QNetworkRequest(request)
        old_proxy = self.proxy()

        splash_proxy_factory = self._getSplashProxyFactory(request)
        if splash_proxy_factory:
            proxy_query = QNetworkProxyQuery(request.url())
            proxy = splash_proxy_factory.queryProxy(proxy_query)[0]
            self.setProxy(proxy)

        # this method is called createRequest, but in fact it creates a reply
        reply = super(ProxiedQNetworkAccessManager, self).createRequest(
            operation, request, outgoingData
        )

        options = {
            'start_time': start_time,
            'operation': operation,
            'outgoingData': outgoingData,
        }

        reply.error.connect(partial(self._handleError, options=options))
        reply.finished.connect(partial(self._handleFinished, options=options))
        reply.metaDataChanged.connect(self._handleMetaData)
        reply.downloadProgress.connect(self._handleDownloadProgress)

        self.setProxy(old_proxy)

        return reply

    def _addHarEntry(self, reply, options):
        cur_time = datetime.datetime.utcnow()
        request = reply.request()

        network_entries = self._getWebPageAttribute(request, 'network_entries')
        if network_entries is not None:
            operation = options['operation']
            outgoingData = options['outgoingData']

            start_time = options['start_time']
            elapsed = (cur_time-start_time).total_seconds()

            network_entries.append({
                # "pageref": "page_0",
                "startedDateTime": options['start_time'].isoformat(),
                "time": elapsed*1000,  # ms
                "request": har.request2har(request, operation, outgoingData),
                "response": har.reply2har(reply),
                # "cache": {},
                # "timings": {},
            })


    def _getSplashProxyFactory(self, request):
        return self._getWebPageAttribute(request, 'splash_proxy_factory')

    def _getWebPageAttribute(self, request, attribute):
        web_frame = request.originatingObject()
        if isinstance(web_frame, QWebFrame):
            return getattr(web_frame.page(), attribute, None)

    def _handleError(self, error_id, options):
        self._addHarEntry(self.sender(), options)
        error_msg = REQUEST_ERRORS.get(error_id, 'unknown error')
        self.log("Download error %d: %s ({url})" % (error_id, error_msg), self.sender(), min_level=1)

    def _handleFinished(self, options):
        reply = self.sender()
        self._addHarEntry(reply, options)
        self.log("Finished downloading {url}", reply)

    def _handleMetaData(self):
        self.log("Headers received for {url}", self.sender(), min_level=3)

    def _handleDownloadProgress(self, received, total):
        if total == -1:
            total = '?'
        self.log("Downloaded %d/%s of {url}" % (received, total), self.sender(), min_level=3)

    def _getSplashRequest(self, request):
        return self._getWebPageAttribute(request, 'splash_request')

    def log(self, msg, reply=None, min_level=2):
        if not reply:
            url = ''
        else:
            url = qurl2ascii(reply.url())
            if not url:
                return
        if self.verbosity >= min_level:
            msg = msg.format(url=url)
            log.msg(msg, system='network')


class SplashQNetworkAccessManager(ProxiedQNetworkAccessManager):
    """
    This QNetworkAccessManager provides:

    * proxy support;
    * request middleware support;
    * additional logging.

    """
    def __init__(self, filters_path, allowed_schemes, verbosity):
        super(SplashQNetworkAccessManager, self).__init__(verbosity=verbosity)

        self.request_middlewares = []
        if self.verbosity >= 2:
            self.request_middlewares.append(RequestLoggingMiddleware())

        if allowed_schemes:
            self.request_middlewares.append(
                AllowedSchemesMiddleware(allowed_schemes, verbosity=verbosity)
            )

        self.request_middlewares.append(AllowedDomainsMiddleware(verbosity=verbosity))

        if filters_path is not None:
            self.adblock_rules = AdblockRulesRegistry(filters_path, verbosity=verbosity)
            self.request_middlewares.append(
                AdblockMiddleware(self.adblock_rules, verbosity=verbosity)
            )
        else:
            self.adblock_rules = None

    def createRequest(self, operation, request, outgoingData=None):
        splash_request = self._getSplashRequest(request)
        if splash_request:
            for filter in self.request_middlewares:
                request = filter.process(request, splash_request, operation, outgoingData)
        return super(SplashQNetworkAccessManager, self).createRequest(operation, request, outgoingData)

    def unknownFilters(self, filter_names):
        names = [f for f in filter_names.split(',') if f]
        if self.adblock_rules is None:
            return names
        return [name for name in names
                if not (self.adblock_rules.filter_is_known(name) or name=='none')]

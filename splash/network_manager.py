# -*- coding: utf-8 -*-
from __future__ import absolute_import
from datetime import datetime
from contextlib import contextmanager

from PyQt4.QtNetwork import (
    QNetworkAccessManager, QNetworkProxyQuery,
    QNetworkReply, QNetworkRequest
)
from PyQt4.QtWebKit import QWebFrame
from twisted.python import log

from splash.qtutils import qurl2ascii, OPERATION_NAMES
from splash import har
from splash.har import qt as har_qt
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

    It also sets up some extra logging, provides a way to get
    the "source" request (that was made to Splash itself) and tracks
    information about requests/responses.
    """

    _REQUEST_ID = QNetworkRequest.User + 1

    REQUEST_CREATED = "created"
    REQUEST_FINISHED = "finished"
    REQUEST_HEADERS_RECEIVED = "headers"

    def __init__(self, verbosity):
        super(ProxiedQNetworkAccessManager, self).__init__()
        self.sslErrors.connect(self._sslErrors)
        self.finished.connect(self._finished)
        self.verbosity = verbosity
        self._next_id = 0

        assert self.proxyFactory() is None, "Standard QNetworkProxyFactory is not supported"

    def _sslErrors(self, reply, errors):
        reply.ignoreSslErrors()

    def _finished(self, reply):
        reply.deleteLater()

    def createRequest(self, operation, request, outgoingData=None):
        """
        This method is called when a new request is sent;
        it must return a reply object to work with.
        """
        start_time = datetime.utcnow()

        request = self._wrapRequest(request)
        har_entry = self._harEntry(request, create=True)
        if har_entry is not None:
            if outgoingData is None:
                bodySize = -1
            else:
                bodySize = outgoingData.size()
            har_entry.update({
                '_tmp': {
                    'start_time': start_time,
                    'request_start_sending_time': start_time,
                    'request_sent_time': start_time,
                    'response_start_time': start_time,

                    # 'outgoingData': outgoingData,
                    'state': self.REQUEST_CREATED,
                },
                "startedDateTime": har.format_datetime(start_time),
                "request": {
                    "method": OPERATION_NAMES.get(operation, '?'),
                    "url": unicode(request.url().toString()),
                    "httpVersion": "HTTP/1.1",
                    "cookies": har_qt.request_cookies2har(request),
                    "queryString": har_qt.querystring2har(request.url()),
                    "headers": har_qt.headers2har(request),

                    "headersSize" : har_qt.headers_size(request),
                    "bodySize": bodySize,
                },
                "response": {
                    "bodySize": -1,
                },
                "cache": {},
                "timings": {
                    "blocked": -1,
                    "dns": -1,
                    "connect": -1,
                    "ssl": -1,

                    "send": 0,
                    "wait": 0,
                    "receive": 0,
                },
                "time": 0,
            })

        with self._proxyApplied(request):
            reply = super(ProxiedQNetworkAccessManager, self).createRequest(
                operation, request, outgoingData
            )
            if har_entry is not None:
                har_entry["response"].update(har_qt.reply2har(reply))

            reply.error.connect(self._handleError)
            reply.finished.connect(self._handleFinished)
            reply.metaDataChanged.connect(self._handleMetaData)
            reply.downloadProgress.connect(self._handleDownloadProgress)

        return reply

    @contextmanager
    def _proxyApplied(self, request):
        """
        This context manager temporary sets a proxy based on request options.
        """
        old_proxy = self.proxy()
        splash_proxy_factory = self._getWebPageAttribute(request, 'splash_proxy_factory')
        if splash_proxy_factory:
            proxy_query = QNetworkProxyQuery(request.url())
            proxy = splash_proxy_factory.queryProxy(proxy_query)[0]
            self.setProxy(proxy)
        try:
            yield
        finally:
            self.setProxy(old_proxy)

    def _wrapRequest(self, request):
        request = QNetworkRequest(request)
        request.setAttribute(self._REQUEST_ID, self._next_id)
        self._next_id += 1
        return request

    def _getRequestId(self, request=None):
        if request is None:
            request = self.sender().request()
        return request.attribute(self._REQUEST_ID).toPyObject()

    def _harEntry(self, request=None, create=False):
        """
        Return a mutable dictionary for request/response
        information storage.
        """
        if request is None:
            request = self.sender().request()

        har_log = self._getWebPageAttribute(request, "har_log")
        if har_log is None:
            return
        return har_log.get_mutable_entry(self._getRequestId(request), create)

    def _getWebPageAttribute(self, request, attribute):
        web_frame = request.originatingObject()
        if isinstance(web_frame, QWebFrame):
            return getattr(web_frame.page(), attribute, None)

    def _handleError(self, error_id):
        error_msg = REQUEST_ERRORS.get(error_id, 'unknown error')
        self.log("Download error %d: %s ({url})" % (error_id, error_msg), self.sender(), min_level=2)

    def _handleFinished(self):
        reply = self.sender()
        har_entry = self._harEntry()
        if har_entry is not None:
            har_entry["_tmp"]["state"] = self.REQUEST_FINISHED

            now = datetime.utcnow()
            start_time = har_entry['_tmp']['start_time']
            response_start_time = har_entry['_tmp']['response_start_time']

            receive_time = har.get_duration(response_start_time, now)
            total_time = har.get_duration(start_time, now)

            har_entry["timings"]["receive"] = receive_time
            har_entry["time"] = total_time

            if not har_entry["timings"]["send"]:
                wait_time = har_entry["timings"]["wait"]
                har_entry["timings"]["send"] = total_time - receive_time - wait_time
                if har_entry["timings"]["send"] < 1e-6:
                    har_entry["timings"]["send"] = 0

            har_entry["response"].update(har_qt.reply2har(reply))

        self.log("Finished downloading {url}", reply)

    def _handleMetaData(self):
        reply = self.sender()
        har_entry = self._harEntry()
        if har_entry is not None:
            if har_entry["_tmp"]["state"] == self.REQUEST_FINISHED:
                self.log("Headers received for {url}; ignoring", reply, min_level=3)
                return

            har_entry["_tmp"]["state"] = self.REQUEST_HEADERS_RECEIVED
            har_entry["response"].update(har_qt.reply2har(reply))

            now = datetime.utcnow()
            request_sent = har_entry["_tmp"]["request_sent_time"]
            har_entry["_tmp"]["response_start_time"] = now
            har_entry["timings"]["wait"] = har.get_duration(request_sent, now)

        self.log("Headers received for {url}", reply, min_level=3)

    def _handleDownloadProgress(self, received, total):
        har_entry = self._harEntry()
        if har_entry is not None:
            har_entry["response"]["bodySize"] = int(received)

        if total == -1:
            total = '?'
        self.log("Downloaded %d/%s of {url}" % (received, total), self.sender(), min_level=4)

    def _handleUploadProgress(self, sent, total):
        har_entry = self._harEntry()
        if har_entry is not None:
            har_entry["request"]["bodySize"] = int(sent)

            now = datetime.utcnow()
            if sent == 0:
                # it is a moment the sending is started
                start_time = har_entry["_tmp"]["request_start_time"]
                har_entry["_tmp"]["request_start_sending_time"] = now
                har_entry["timings"]["blocked"] = har.get_duration(start_time, now)

            har_entry["_tmp"]["request_sent_time"] = now

            if sent == total:
                har_entry["_tmp"]["response_start_time"] = now
                start_sending_time = har_entry["_tmp"]["request_start_sending_time"]
                har_entry["timings"]["send"] = har.get_duration(start_sending_time, now)

        if total == -1:
            total = '?'
        self.log("Uploaded %d/%s of {url}" % (sent, total), self.sender(), min_level=4)

    def _getRenderOptions(self, request):
        return self._getWebPageAttribute(request, 'render_options')

    def log(self, msg, reply=None, min_level=2):
        if self.verbosity < min_level:
            return

        if not reply:
            url = ''
        else:
            url = qurl2ascii(reply.url())
            if not url:
                return

        msg = msg.format(url=url)
        log.msg(msg, system='network-manager')


class SplashQNetworkAccessManager(ProxiedQNetworkAccessManager):
    """
    This QNetworkAccessManager provides:

    * proxy support;
    * request middleware support;
    * additional logging.

    """
    adblock_rules = None

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

    def createRequest(self, operation, request, outgoingData=None):
        render_options = self._getRenderOptions(request)
        if render_options:
            for filter in self.request_middlewares:
                request = filter.process(request, render_options, operation, outgoingData)
        return super(SplashQNetworkAccessManager, self).createRequest(operation, request, outgoingData)

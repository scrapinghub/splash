# -*- coding: utf-8 -*-
from __future__ import absolute_import
from datetime import datetime
import traceback
from contextlib import contextmanager
import itertools

from PyQt5.QtNetwork import (
    QNetworkAccessManager,
    QNetworkProxyQuery,
    QNetworkRequest,
    QNetworkReply,
    QNetworkCookieJar
)
from PyQt5.QtWebKitWidgets import QWebFrame
from twisted.python import log

from splash.qtutils import qurl2ascii, REQUEST_ERRORS
from splash import har
from splash.har import qt as har_qt
from splash.request_middleware import (
    AdblockMiddleware,
    AllowedDomainsMiddleware,
    AllowedSchemesMiddleware,
    RequestLoggingMiddleware,
    AdblockRulesRegistry,
)
from splash.response_middleware import ContentTypeMiddleware
from splash import defaults


def create_default(filters_path=None, verbosity=None, allowed_schemes=None):
    verbosity = defaults.VERBOSITY if verbosity is None else verbosity
    if allowed_schemes is None:
        allowed_schemes = defaults.ALLOWED_SCHEMES
    else:
        allowed_schemes = allowed_schemes.split(',')
    manager = SplashQNetworkAccessManager(
        filters_path=filters_path,
        allowed_schemes=allowed_schemes,
        verbosity=verbosity
    )
    manager.setCache(None)
    return manager


class ProxiedQNetworkAccessManager(QNetworkAccessManager):
    """
    QNetworkAccessManager subclass with extra features. It

    * Enables "splash proxy factories" support. Qt provides similar
      functionality via setProxyFactory method, but standard
      QNetworkProxyFactory is not flexible enough.
    * Sets up extra logging.
    * Provides a way to get the "source" request (that was made to Splash
      itself).
    * Tracks information about requests/responses and stores it in HAR format.

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

        self._request_ids = itertools.count()
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
        self._handle_custom_headers(request)
        self._handle_request_cookies(request)

        with self._proxyApplied(request):
            callbacks = self._getWebPageAttribute(request, "callbacks")
            if callbacks and 'on_request' in callbacks:
                for cb in callbacks["on_request"]:
                    try:
                        cb(request, operation, outgoingData)
                    except:
                        # Unhandled exceptions in createRequest method cause
                        # segfaults, so we log all errors.
                        self.log("error in on_resource_requested callback", min_level=1)
                        self.log(traceback.format_exc(), min_level=1)

            if hasattr(request, 'custom_proxy'):
                self.setProxy(request.custom_proxy)

            har_entry = self._harEntry(request, create=True)
            if har_entry is not None:
                har_entry.update(self._initialHarData(
                    start_time=start_time,
                    operation=operation,
                    request=request,
                    outgoingData=outgoingData
                ))

            reply = super(ProxiedQNetworkAccessManager, self).createRequest(
                operation, request, outgoingData
            )
            if har_entry is not None:
                har_entry["response"].update(har_qt.reply2har(reply))

            reply.error.connect(self._handleError)
            reply.finished.connect(self._handleFinished)
            # http://doc.qt.io/qt-5/qnetworkreply.html#metaDataChanged
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
        request.setAttribute(self._REQUEST_ID, next(self._request_ids))
        return request

    def _initialHarData(self, start_time, operation, request, outgoingData):
        """ Return initial values for HAR entry """
        return {
            '_tmp': {
                'start_time': start_time,
                'request_start_sending_time': start_time,
                'request_sent_time': start_time,
                'response_start_time': start_time,

                # 'outgoingData': outgoingData,
                'state': self.REQUEST_CREATED,
            },
            "startedDateTime": har.format_datetime(start_time),
            "request": har_qt.request2har(request, operation, outgoingData),
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
        }

    def _handle_custom_headers(self, request):
        if self._getWebPageAttribute(request, "skip_custom_headers"):
            # XXX: this hack assumes that new requests between
            # BrowserTab._create_request and this function are not possible,
            # i.e. we don't give control to the event loop in between.
            # Unfortunately we can't store this flag on a request itself
            # because a new QNetworkRequest instance is created by QWebKit.
            self._setWebPageAttribute(request, "skip_custom_headers", False)
            return

        headers = self._getWebPageAttribute(request, "custom_headers")

        if isinstance(headers, dict):
            headers = headers.items()

        for name, value in headers or []:
            request.setRawHeader(name, value)

    def _handle_request_cookies(self, request):
        jar = QNetworkCookieJar()
        self.setCookieJar(jar)
        cookiejar = self._getWebPageAttribute(request, "cookiejar")
        if cookiejar is not None:
            cookiejar.update_cookie_header(request)

    def _handle_reply_cookies(self, reply):
        cookiejar = self._getWebPageAttribute(reply.request(), "cookiejar")
        if cookiejar is not None:
            cookiejar.fill_from_reply(reply)

    def _getRequestId(self, request=None):
        if request is None:
            request = self.sender().request()
        return request.attribute(self._REQUEST_ID)

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

    def _setWebPageAttribute(self, request, attribute, value):
        web_frame = request.originatingObject()
        if isinstance(web_frame, QWebFrame):
            return setattr(web_frame.page(), attribute, value)

    def _handleError(self, error_id):
        if error_id != QNetworkReply.OperationCanceledError:
            error_msg = REQUEST_ERRORS.get(error_id, 'unknown error')
            self.log('Download error %d: %s ({url})' % (error_id, error_msg),
                     self.sender(), min_level=2)

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
        """Signal emitted before reading response body, after getting headers
        """
        reply = self.sender()
        self._handle_reply_cookies(reply)

        callbacks = self._getWebPageAttribute(reply.request(), "callbacks")

        if callbacks and "on_response_headers" in callbacks:
            for cb in callbacks["on_response_headers"]:
                try:
                    cb(reply)
                except:
                    # TODO unhandled exceptions in lua callbacks
                    # should we raise errors here?
                    # https://github.com/scrapinghub/splash/issues/161
                    self.log("error in on_response_headers callback", min_level=1)
                    self.log(traceback.format_exc(), min_level=1)

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
        self.response_middlewares = []

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

        self.response_middlewares.append(ContentTypeMiddleware(self.verbosity))

    def run_response_middlewares(self):
        reply = self.sender()
        reply.metaDataChanged.disconnect(self.run_response_middlewares)
        render_options = self._getRenderOptions(reply.request())
        if render_options:
            for middleware in self.response_middlewares:
                middleware.process(reply, render_options)

    def createRequest(self, operation, request, outgoingData=None):
        render_options = self._getRenderOptions(request)
        if render_options:
            for filter in self.request_middlewares:
                request = filter.process(request, render_options, operation, outgoingData)
        reply = super(SplashQNetworkAccessManager, self).createRequest(operation, request, outgoingData)
        if render_options:
            reply.metaDataChanged.connect(self.run_response_middlewares)
        return reply

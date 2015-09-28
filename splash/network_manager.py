# -*- coding: utf-8 -*-
from __future__ import absolute_import
import itertools
import functools
from datetime import datetime
import traceback

from PyQt4.QtCore import QTimer
from PyQt4.QtNetwork import (
    QNetworkAccessManager,
    QNetworkProxyQuery,
    QNetworkRequest,
    QNetworkReply,
    QNetworkCookieJar
)
from twisted.python import log

from splash.qtutils import qurl2ascii, REQUEST_ERRORS, get_request_webframe
from splash.request_middleware import (
    AdblockMiddleware,
    AllowedDomainsMiddleware,
    AllowedSchemesMiddleware,
    RequestLoggingMiddleware,
    AdblockRulesRegistry,
    ResourceTimeoutMiddleware)
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
    * Allows to set per-request timeouts.

    """

    _REQUEST_ID = QNetworkRequest.User + 1

    def __init__(self, verbosity):
        super(ProxiedQNetworkAccessManager, self).__init__()
        self.sslErrors.connect(self._on_ssl_errors)
        self.finished.connect(self._on_finished)
        self.verbosity = verbosity
        self._reply_timeout_timers = {}  # requestId => timer
        self._default_proxy = self.proxy()

        self._request_ids = itertools.count()
        assert self.proxyFactory() is None, "Standard QNetworkProxyFactory is not supported"

    def _on_ssl_errors(self, reply, errors):
        reply.ignoreSslErrors()

    def _on_finished(self, reply):
        reply.deleteLater()

    def createRequest(self, operation, request, outgoingData=None):
        """
        This method is called when a new request is sent;
        it must return a reply object to work with.
        """
        start_time = datetime.utcnow()

        # Proxies are managed per-request, so we're restoring a default
        # before each request. This assumes all requests go through
        # this method.
        self._clear_proxy()

        request, req_id = self._wrap_request(request)
        self._handle_custom_headers(request)
        self._handle_request_cookies(request)

        self._run_webpage_callbacks(request, 'on_request',
                                    request, operation, outgoingData)

        self._handle_custom_proxies(request)

        har = self._get_har(request)
        if har is not None:
            har.store_new_request(
                req_id=req_id,
                start_time=start_time,
                operation=operation,
                request=request,
                outgoingData=outgoingData,
            )

        reply = super(ProxiedQNetworkAccessManager, self).createRequest(
            operation, request, outgoingData
        )

        if hasattr(request, 'timeout'):
            timeout = request.timeout * 1000
            if timeout:
                self._set_reply_timeout(reply, timeout)

        if har is not None:
            har.store_new_reply(req_id, reply)

        reply.error.connect(self._on_reply_error)
        reply.finished.connect(self._on_reply_finished)
        # http://doc.qt.io/qt-5/qnetworkreply.html#metaDataChanged
        reply.metaDataChanged.connect(self._on_reply_headers)
        reply.downloadProgress.connect(self._on_reply_download_progress)
        return reply

    def _set_reply_timeout(self, reply, timeout_ms):
        request_id = self._get_request_id(reply.request())
        # reply is used as a parent for the timer in order to destroy
        # the timer when reply is destroyed. It segfaults otherwise.
        timer = QTimer(reply)
        timer.setSingleShot(True)
        timer_callback = functools.partial(self._on_reply_timeout,
                                           reply=reply,
                                           timer=timer,
                                           request_id=request_id)
        timer.timeout.connect(timer_callback)
        self._reply_timeout_timers[request_id] = timer
        timer.start(timeout_ms)

    def _on_reply_timeout(self, reply, timer, request_id):
        self._reply_timeout_timers.pop(request_id)
        self.log("timed out, aborting: {url}", reply, min_level=1)
        # FIXME: set proper error code
        reply.abort()

    def _cancel_reply_timer(self, reply):
        request_id = self._get_request_id(reply.request())
        timer = self._reply_timeout_timers.pop(request_id, None)
        if timer and timer.isActive():
            timer.stop()

    def _clear_proxy(self):
        """ Init default proxy """
        self.setProxy(self._default_proxy)

    def _wrap_request(self, request):
        req = QNetworkRequest(request)
        req_id = next(self._request_ids)
        req.setAttribute(self._REQUEST_ID, req_id)
        if hasattr(request, 'timeout'):
            req.timeout = request.timeout
        return req, req_id

    def _handle_custom_proxies(self, request):
        # proxies set in proxy profiles or `proxy` HTTP argument
        splash_proxy_factory = self._get_webpage_attribute(request, 'splash_proxy_factory')
        if splash_proxy_factory:
            proxy_query = QNetworkProxyQuery(request.url())
            proxy = splash_proxy_factory.queryProxy(proxy_query)[0]
            self.setProxy(proxy)

        # proxies set in on_request
        if hasattr(request, 'custom_proxy'):
            self.setProxy(request.custom_proxy)

    def _handle_custom_headers(self, request):
        if self._get_webpage_attribute(request, "skip_custom_headers"):
            # XXX: this hack assumes that new requests between
            # BrowserTab._create_request and this function are not possible,
            # i.e. we don't give control to the event loop in between.
            # Unfortunately we can't store this flag on a request itself
            # because a new QNetworkRequest instance is created by QWebKit.
            self._set_webpage_attribute(request, "skip_custom_headers", False)
            return

        headers = self._get_webpage_attribute(request, "custom_headers")

        if isinstance(headers, dict):
            headers = headers.items()

        for name, value in headers or []:
            request.setRawHeader(name, value)

    def _handle_request_cookies(self, request):
        jar = QNetworkCookieJar()
        self.setCookieJar(jar)
        cookiejar = self._get_webpage_attribute(request, "cookiejar")
        if cookiejar is not None:
            cookiejar.update_cookie_header(request)

    def _handle_reply_cookies(self, reply):
        cookiejar = self._get_webpage_attribute(reply.request(), "cookiejar")
        if cookiejar is not None:
            cookiejar.fill_from_reply(reply)

    def _get_request_id(self, request=None):
        if request is None:
            request = self.sender().request()
        return request.attribute(self._REQUEST_ID).toPyObject()

    def _get_har(self, request=None):
        """
        Return HarBuilder instance.
        :rtype: splash.har_builder.HarBuilder | None
        """
        if request is None:
            request = self.sender().request()
        return self._get_webpage_attribute(request, "har")

    def _get_webpage_attribute(self, request, attribute):
        web_frame = get_request_webframe(request)
        if web_frame:
            return getattr(web_frame.page(), attribute, None)

    def _set_webpage_attribute(self, request, attribute, value):
        web_frame = get_request_webframe(request)
        if web_frame:
            return setattr(web_frame.page(), attribute, value)

    def _on_reply_error(self, error_id):
        if error_id != QNetworkReply.OperationCanceledError:
            error_msg = REQUEST_ERRORS.get(error_id, 'unknown error')
            self.log('Download error %d: %s ({url})' % (error_id, error_msg),
                     self.sender(), min_level=2)

    def _on_reply_finished(self):
        reply = self.sender()
        request = reply.request()
        self._cancel_reply_timer(reply)
        har = self._get_har()
        har_entry = None
        if har is not None:
            req_id = self._get_request_id()
            har.store_reply_finished(req_id, reply)
            # We're passing HAR entry because reply object itself doesn't
            # have all information.
            har_entry = har.get_entry(req_id)

        self._run_webpage_callbacks(request, "on_response", reply, har_entry)
        self.log("Finished downloading {url}", reply)

    def _on_reply_headers(self):
        """Signal emitted before reading response body, after getting headers
        """
        reply = self.sender()
        request = reply.request()
        self._handle_reply_cookies(reply)
        self._run_webpage_callbacks(request, "on_response_headers", reply)

        har = self._get_har()
        if har is not None:
            har.store_reply_headers_received(self._get_request_id(), reply)

        self.log("Headers received for {url}", reply, min_level=3)

    def _on_reply_download_progress(self, received, total):
        har = self._get_har()
        if har is not None:
            req_id = self._get_request_id()
            har.store_reply_download_progress(req_id, received, total)

        if total == -1:
            total = '?'
        self.log("Downloaded %d/%s of {url}" % (received, total),
                 self.sender(), min_level=4)

    def _on_reply_upload_progress(self, sent, total):
        # FIXME: is it used?
        har = self._get_har()
        if har is not None:
            req_id = self._get_request_id()
            har.store_request_upload_progress(req_id, sent, total)

        if total == -1:
            total = '?'
        self.log("Uploaded %d/%s of {url}" % (sent, total),
                 self.sender(), min_level=4)

    def _get_render_options(self, request):
        return self._get_webpage_attribute(request, 'render_options')

    def _run_webpage_callbacks(self, request, event_name, *args):
        callbacks = self._get_webpage_attribute(request, "callbacks")
        if not callbacks:
            return
        for cb in callbacks.get(event_name, []):
            try:
                cb(*args)
            except:
                # TODO unhandled exceptions in lua callbacks
                # should we raise errors here?
                # https://github.com/scrapinghub/splash/issues/161
                self.log("error in %s callback" % event_name, min_level=1)
                # Log the traceback. It requires escaping because
                # self.log uses str.format.
                tb = traceback.format_exc().replace('{', '{{').replace('}', '}}')
                self.log(tb, min_level=1)

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
        self.request_middlewares.append(ResourceTimeoutMiddleware())

        if filters_path is not None:
            self.adblock_rules = AdblockRulesRegistry(filters_path, verbosity=verbosity)
            self.request_middlewares.append(
                AdblockMiddleware(self.adblock_rules, verbosity=verbosity)
            )

        self.response_middlewares.append(ContentTypeMiddleware(self.verbosity))

    def run_response_middlewares(self):
        reply = self.sender()
        reply.metaDataChanged.disconnect(self.run_response_middlewares)
        render_options = self._get_render_options(reply.request())
        if render_options:
            for middleware in self.response_middlewares:
                middleware.process(reply, render_options)

    def createRequest(self, operation, request, outgoingData=None):
        render_options = self._get_render_options(request)
        if render_options:
            for middleware in self.request_middlewares:
                request = middleware.process(request, render_options, operation, outgoingData)
        reply = super(SplashQNetworkAccessManager, self).createRequest(operation, request, outgoingData)
        if render_options:
            reply.metaDataChanged.connect(self.run_response_middlewares)
        return reply

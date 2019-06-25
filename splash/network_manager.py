# -*- coding: utf-8 -*-
import base64
import itertools
import functools
from datetime import datetime
import traceback

from PyQt5.QtCore import QByteArray, QTimer
from PyQt5.QtNetwork import (
    QNetworkAccessManager,
    QNetworkProxyQuery,
    QNetworkRequest,
    QNetworkReply
)
from twisted.python import log

from splash.qtutils import qurl2ascii, REQUEST_ERRORS, get_request_webframe
from splash.request_middleware import (
    AdblockMiddleware,
    AllowedDomainsMiddleware,
    AllowedSchemesMiddleware,
    RequestLoggingMiddleware,
    AdblockRulesRegistry,
    ResourceTimeoutMiddleware,
    RequestResponseBodyTrackingMiddleware,
)
from splash.response_middleware import ContentTypeMiddleware
from splash import defaults
from splash.qtutils import qt_header_items
from splash.utils import to_bytes
from splash.cookies import SplashCookieJar


class _InvalidContentLength(ValueError):

    def __init__(self, value):
        if isinstance(value, bytes):
            value = '0x' + value.hex()
        message = 'Invalid Content-Length header value: {}'.format(value)
        super().__init__(message)


def _get_content_length(reply):
    for name, value in qt_header_items(reply):
        if bytes(name).lower() == b'content-length':
            value = bytes(value).split(b',', 1)[0]
            try:
                value = value.decode('latin1')
                value = int(value)
            except (UnicodeDecodeError, ValueError):
                raise _InvalidContentLength(value)
            if value < 0:
                raise _InvalidContentLength(value)
            return value


def _size_warrants_abort(sizes_and_sources, render_options, log, reply):
    if render_options is None:
        return False
    option = "response_size_limit"
    max_size = render_options.get(option, None)
    if max_size is not None:
        try:
            max_size = int(max_size)
        except ValueError:
            log("Non-integer value received for rendering option '{}': {}"
                .format(option, max_size), min_level=1)
            log(traceback.format_exc(), min_level=1, format_msg=False)
            max_size = None
        else:
            if max_size < 0:
                log("The value of rendering option '{}' ({}) must be 0 or "
                    "higher.".format(option, max_size),min_level=1)
                max_size = None
            elif (render_options.max_response_size_limit is not None and
                    max_size > render_options.max_response_size_limit):
                log("The value of rendering option '{}' ({}) exceeds the "
                    "maximum value allowed.".format(option, max_size),
                    min_level=1)
                max_size = None
    if max_size is None:
        if render_options.max_response_size_limit is not None:
            max_size = render_options.max_response_size_limit
        else:
            max_size = defaults.RESPONSE_SIZE_LIMIT
        if max_size is None:
            return False
    for size, source in sizes_and_sources:
        if size is None:
            continue
        if size <= max_size:
            continue
        log("The {} ({}) exceeds the maximum response size ({}), aborting: "
            "{{url}}".format(source, size, max_size), reply, min_level=1)
        log(render_options, reply, min_level=1, format_msg=False)
        return True
    return False


class NetworkManagerFactory(object):
    def __init__(self, filters_path=None, verbosity=None, allowed_schemes=None, disable_browser_caches=None):
        verbosity = defaults.VERBOSITY if verbosity is None else verbosity
        self.verbosity = verbosity
        self.disable_browser_caches = disable_browser_caches
        self.request_middlewares = []
        self.response_middlewares = []
        self.adblock_rules = None

        # Initialize request and response middlewares
        allowed_schemes = (defaults.ALLOWED_SCHEMES if allowed_schemes is None
                           else allowed_schemes.split(','))
        if allowed_schemes:
            self.request_middlewares.append(
                AllowedSchemesMiddleware(allowed_schemes, verbosity=verbosity)
            )

        if self.verbosity >= 2:
            self.request_middlewares.append(RequestLoggingMiddleware())

        self.request_middlewares.append(AllowedDomainsMiddleware(verbosity=verbosity))
        self.request_middlewares.append(ResourceTimeoutMiddleware())
        self.request_middlewares.append(RequestResponseBodyTrackingMiddleware())

        if filters_path is not None:
            self.adblock_rules = AdblockRulesRegistry(filters_path, verbosity=verbosity)
            self.request_middlewares.append(
                AdblockMiddleware(self.adblock_rules, verbosity=verbosity)
            )

        self.response_middlewares.append(ContentTypeMiddleware(self.verbosity))

    def __call__(self):
        manager = SplashQNetworkAccessManager(
            request_middlewares=self.request_middlewares,
            response_middlewares=self.response_middlewares,
            verbosity=self.verbosity,
            disable_browser_caches=self.disable_browser_caches,
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
    * Tracks information about requests/responses and stores it in HAR format,
      including request and response content.
    * Allows to set per-request timeouts.
    * Handles per-request response size limits.
    """
    _REQUEST_ID = QNetworkRequest.User + 1
    _SHOULD_TRACK = QNetworkRequest.User + 2

    def __init__(self, verbosity, disable_browser_caches):
        super(ProxiedQNetworkAccessManager, self).__init__()
        self.sslErrors.connect(self._on_ssl_errors)
        self.finished.connect(self._on_finished)
        self.verbosity = verbosity
        self.disable_browser_caches = disable_browser_caches
        self._reply_timeout_timers = {}  # requestId => timer
        self._default_proxy = self.proxy()
        self.cookiejar = SplashCookieJar(self)
        self.setCookieJar(self.cookiejar)
        self._response_bodies = {}  # requestId => response content
        self._request_ids = itertools.count()
        assert self.proxyFactory() is None, "Standard QNetworkProxyFactory is not supported"

    def _on_ssl_errors(self, reply, errors):
        reply.ignoreSslErrors()

    def _on_finished(self, reply):
        reply.deleteLater()

    def createRequest(self, operation, request, outgoingData=None):
        try:
            return self._createRequest(operation, request, outgoingData=outgoingData)
        except:
            # There are too many errors that can happen in NAT, in case something happens
            # splash will segfault. To avoid this in case of Splash NAT error we will just
            # delegate to superclass (no splash intervention).
            # WARNING: this can hide error from user (no more segfault on error, and response will be 200,
            # but without intended splash behavior). This is not perfect but is better than crash.
            self.log("internal error in _createRequest middleware", min_level=1)
            self.log(traceback.format_exc(), min_level=1, format_msg=False)
            return super(ProxiedQNetworkAccessManager, self).createRequest(operation, request, outgoingData)

    def _get_request_body(self, request, outgoing_data):
        if outgoing_data is None:
            return

        size = None
        if outgoing_data.isSequential():
            # In a sequential QIODevice, size() returns the value of
            # bytesAvailable(), which is only the size of the data in the
            # QIODevice buffer and not the total size of the output. Until
            # a read attempt, the buffer is empty and size() returns zero.
            #
            # In requests generated by Qt WebKit, outgoing_data is a
            # WebCore::FormDataIODevice object, which is sequential. Its
            # getFormDataSize() method cannot be accessed through PyQt5,
            # but Qt WebKit puts its value in the Content-Length header
            # (see WebCore::QNetworkReplyHandler::getIODevice).
            header = request.header(QNetworkRequest.ContentLengthHeader)
            if isinstance(header, int):
                size = header
            else:
                self.log(("non-integer QNetworkRequest Content-Length "
                          "header value %r") % (size,),
                         min_level=1)
        else:
            size = outgoing_data.size()

        if size is not None:
            body = bytes(outgoing_data.peek(size))
            if len(body) != size:
                self.log(("request body of size %s but Content-Length "
                          "header value %s") % (len(body), size),
                         min_level=1)
            return body

    def _createRequest(self, operation, request, outgoingData=None):
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

        if getattr(request, 'track_request_body', False):
            content = self._get_request_body(request, outgoingData)
        else:
            content = None

        self._handle_custom_headers(request)
        self._handle_request_cookies(request)

        self._run_webpage_callbacks(request, 'on_request',
                                    request, operation, content)

        self._handle_custom_proxies(request)
        self._handle_request_response_tracking(request)

        har = self._get_har(request)
        if har is not None:
            har.store_new_request(
                req_id=req_id,
                start_time=start_time,
                operation=operation,
                request=request,
                content=content
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

        if self._should_track_content(request):
            self._response_bodies[req_id] = QByteArray()
            reply.readyRead.connect(self._on_reply_ready_read)

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

        if self.disable_browser_caches:
            # disables the network cache
            # see http://doc.qt.io/qt-5/qnetworkrequest.html#CacheLoadControl-enum
            req.setAttribute(QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.AlwaysNetwork)
            req.setAttribute(QNetworkRequest.CacheSaveControlAttribute, False)

        for attr in ['timeout', 'track_request_body', 'track_response_body']:
            if hasattr(request, attr):
                setattr(req, attr, getattr(request, attr))
        return req, req_id

    def _handle_custom_proxies(self, request):
        proxy = None

        # proxies set in proxy profiles or `proxy` HTTP argument
        splash_proxy_factory = self._get_webpage_attribute(request, 'splash_proxy_factory')
        if splash_proxy_factory:
            proxy_query = QNetworkProxyQuery(request.url())
            proxy = splash_proxy_factory.queryProxy(proxy_query)[0]
            self.setProxy(proxy)

        # proxies set in on_request
        if hasattr(request, 'custom_proxy'):
            proxy = request.custom_proxy
            self.setProxy(proxy)

        # Handle proxy auth. We're setting Proxy-Authorization header
        # explicitly because Qt loves to cache proxy credentials.
        if proxy is None:
            return
        user, password = proxy.user(), proxy.password()
        if not user and not password:
            return
        auth = b"Basic " + base64.b64encode("{}:{}".format(user, password).encode("utf-8"))
        request.setRawHeader(b"Proxy-Authorization", auth)

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
            try:
                if isinstance(value, (int, float)):
                    value = str(value)
                request.setRawHeader(to_bytes(name), to_bytes(value))
            except TypeError:
                msg = "invalid header {!r}: {!r}. Header keys and values must be strings or bytes"
                self.log(msg.format(name, value), min_level=1, format_msg=False)
                continue

    def _handle_request_cookies(self, request):
        self.cookiejar.update_cookie_header(request)

    def _handle_reply_cookies(self, reply):
        self.cookiejar.fill_from_reply(reply)

    def _handle_request_response_tracking(self, request):
        track = getattr(request, 'track_response_body', False)
        request.setAttribute(self._SHOULD_TRACK, track)

    def _should_track_content(self, request):
        return request.attribute(self._SHOULD_TRACK)

    def _get_request_id(self, request=None):
        if request is None:
            request = self.sender().request()
        return request.attribute(self._REQUEST_ID)

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
        self._response_bodies.pop(self._get_request_id(), None)

        if error_id != QNetworkReply.OperationCanceledError:
            error_msg = REQUEST_ERRORS.get(error_id, 'unknown error')
            self.log('Download error %d: %s ({url})' % (error_id, error_msg),
                     self.sender(), min_level=2)

    def _on_reply_ready_read(self):
        reply = self.sender()
        self._store_response_chunk(reply)

    def _store_response_chunk(self, reply):
        req_id = self._get_request_id(reply.request())
        if req_id not in self._response_bodies:
            self.log("Internal problem in _store_response_chunk: "
                     "request %s is not tracked" % req_id, reply, min_level=1)
            return
        chunk = reply.peek(reply.bytesAvailable())
        self._response_bodies[req_id].append(chunk)

    def _on_reply_finished(self):
        reply = self.sender()
        request = reply.request()
        self._cancel_reply_timer(reply)
        har = self._get_har()
        har_entry, content = None, None
        if har is not None:
            req_id = self._get_request_id()
            # FIXME: what if har is None? When can it be None?
            # Who removes the content from self._response_bodies dict?
            content = self._response_bodies.pop(req_id, None)
            if content is not None:
                content = bytes(content)

            # FIXME: content is kept in memory at least twice,
            # as raw data and as a base64-encoded copy.
            har.store_reply_finished(req_id, reply, content)
            har_entry = har.get_entry(req_id)

        # We're passing HAR entry to the callbacks because reply object
        # itself doesn't have all information.
        # Content is passed in order to avoid decoding it from base64.
        self._run_webpage_callbacks(request, "on_response", reply, har_entry,
                                    content)
        self.log("Finished downloading {url}", reply)

    def _size_caused_abort(self, sizes_and_sources):
        reply = self.sender()
        request = reply.request()
        render_options = self._get_render_options(request)
        if _size_warrants_abort(
                sizes_and_sources, render_options, self.log, reply):
            reply.abort()
            return True
        return False

    def _on_reply_headers(self):
        """Signal emitted before reading response body, after getting headers
        """
        reply = self.sender()
        request = reply.request()

        try:
            content_length = _get_content_length(reply)
        except _InvalidContentLength as error:
            self.log("On response from {{url}}: {}".format(error),
                     reply, min_level=3)
            content_length = None
        sizes_and_sources = ((content_length, "Content-Length header"),)
        if self._size_caused_abort(sizes_and_sources):
            return

        self._handle_reply_cookies(reply)
        self._run_webpage_callbacks(request, "on_response_headers", reply)

        har = self._get_har()
        if har is not None:
            har.store_reply_headers_received(self._get_request_id(request), reply)

        self.log("Headers received for {url}", reply, min_level=3)

    def _on_reply_download_progress(self, received, total):
        reply = self.sender()
        request = reply.request()

        sizes_and_sources = (
            (total, "expected response size"),
            (received, "size of the response content downloaded so far"),
        )
        if self._size_caused_abort(sizes_and_sources):
            return

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
        run_callbacks = self._get_webpage_attribute(request, "run_callbacks")
        if run_callbacks:
            run_callbacks(event_name, *args)

    def log(self, msg, reply=None, min_level=2, format_msg=True):
        if self.verbosity < min_level:
            return

        if not reply:
            url = ''
        else:
            url = qurl2ascii(reply.url())
            if not url:
                return

        if format_msg:
            msg = msg.format(url=url)
        log.msg(msg, system='network-manager')


class SplashQNetworkAccessManager(ProxiedQNetworkAccessManager):
    """
    This QNetworkAccessManager provides:

    * proxy support;
    * request middleware support;
    * additional logging.

    """
    def __init__(self, request_middlewares, response_middlewares, verbosity, disable_browser_caches=None):
        super(SplashQNetworkAccessManager, self).__init__(verbosity=verbosity, disable_browser_caches=disable_browser_caches)
        self.request_middlewares = request_middlewares
        self.response_middlewares = response_middlewares
        self.disable_browser_caches = disable_browser_caches

    def run_response_middlewares(self):
        reply = self.sender()
        reply.metaDataChanged.disconnect(self.run_response_middlewares)
        render_options = self._get_render_options(reply.request())
        if render_options:
            try:
                for middleware in self.response_middlewares:
                    middleware.process(reply, render_options)
            except:
                self.log("internal error in response middleware", min_level=1)
                self.log(traceback.format_exc(), min_level=1, format_msg=False)

    def createRequest(self, operation, request, outgoingData=None):
        # XXX: This method MUST return a reply, otherwise PyQT segfaults.
        render_options = self._get_render_options(request)
        if render_options:
            try:
                for middleware in self.request_middlewares:
                    request = middleware.process(request, render_options, operation, outgoingData)
            except:
                self.log("internal error in request middleware", min_level=1)
                self.log(traceback.format_exc(), min_level=1, format_msg=False)

        reply = super(SplashQNetworkAccessManager, self).createRequest(operation, request, outgoingData)
        if render_options:
            reply.metaDataChanged.connect(self.run_response_middlewares)
        return reply

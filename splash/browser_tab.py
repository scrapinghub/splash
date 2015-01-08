# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import base64
import copy
import pprint
import weakref
import functools
from PyQt4.QtWebKit import QWebPage, QWebSettings, QWebView
from PyQt4.QtCore import (Qt, QUrl, QBuffer, QSize, QTimer, QObject,
                          pyqtSlot)
from PyQt4.QtGui import QPainter, QImage, QMouseEvent, QKeyEvent
from PyQt4.QtNetwork import QNetworkRequest
from twisted.internet import defer
from twisted.python import log
from splash import defaults
from splash.utils import parse_viewport
from splash.qtutils import qurl2ascii, OPERATION_QT_CONSTANTS, qt2py, WrappedSignal
from splash.har.qt import cookies2har
from splash.har.utils import without_private

from .qwebpage import SplashQWebPage


def skip_if_closing(meth):
    @functools.wraps(meth)
    def wrapped(self, *args, **kwargs):
        if self._closing:
            self.logger.log("%s is not called because BrowserTab is closing" % meth.__name__, min_level=2)
            return
        return meth(self, *args, **kwargs)
    return wrapped


class BrowserTab(QObject):
    """
    An object for controlling a single browser tab (QWebView).

    It is created by splash.pool.Pool. Pool attaches to tab's deferred
    and waits until either a callback or an errback is called, then destroys
    a BrowserTab.

    XXX: currently cookies are not shared between "browser tabs".
    """

    def __init__(self, network_manager, splash_proxy_factory, verbosity,
                 render_options):
        """ Create a new browser tab. """
        QObject.__init__(self)
        self.deferred = defer.Deferred()
        self.network_manager = network_manager
        self.verbosity = verbosity
        self._uid = render_options.get_uid()
        self._closing = False
        self._active_timers = set()
        self._timers_to_cancel_on_redirect = weakref.WeakKeyDictionary()  # timer: callback
        self._timers_to_cancel_on_error = weakref.WeakKeyDictionary()  # timer: callback
        self._js_console = None
        self._history = []
        self._autoload_scripts = []

        self._init_webpage(verbosity, network_manager, splash_proxy_factory,
                           render_options)
        self._setup_logging(verbosity)
        self.http_client = _SplashHttpClient(self.web_page)

    def _init_webpage(self, verbosity, network_manager, splash_proxy_factory, render_options):
        """ Create and initialize QWebPage and QWebView """
        self.web_page = SplashQWebPage(verbosity)
        self.web_page.setNetworkAccessManager(network_manager)
        self.web_page.splash_proxy_factory = splash_proxy_factory
        self.web_page.render_options = render_options

        self._set_default_webpage_options(self.web_page)
        self._setup_webpage_events()

        self.web_view = QWebView()
        geometry = render_options.get_geometry()
        self.web_view.setGeometry(0, 0, *parse_viewport(geometry))
        self.web_view.setPage(self.web_page)
        self.web_view.setAttribute(Qt.WA_DeleteOnClose, True)

    def _set_default_webpage_options(self, web_page):
        """
        Set QWebPage options.
        TODO: allow to customize them.
        """
        settings = web_page.settings()
        settings.setAttribute(QWebSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebSettings.PluginsEnabled, False)
        settings.setAttribute(QWebSettings.PrivateBrowsingEnabled, True)
        settings.setAttribute(QWebSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebSettings.LocalContentCanAccessRemoteUrls, True)
        web_page.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        web_page.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)

    def _setup_logging(self, verbosity):
        """ Setup logging of various events """
        self.logger = _BrowserTabLogger(
            uid=self._uid,
            web_page=self.web_page,
            verbosity=verbosity,
        )
        self.logger.enable()

    def _setup_webpage_events(self):
        self._load_finished = WrappedSignal(self.web_page.mainFrame().loadFinished)
        self.web_page.mainFrame().loadFinished.connect(self._on_load_finished)
        self.web_page.mainFrame().urlChanged.connect(self._on_url_changed)
        self.web_page.mainFrame().javaScriptWindowObjectCleared.connect(self._on_javascript_window_object_cleared)

    def return_result(self, result):
        """ Return a result to the Pool. """
        if self._result_already_returned():
            self.logger.log("error: result is already returned", min_level=1)

        self.deferred.callback(result)
        # self.deferred = None

    def return_error(self, error=None):
        """ Return an error to the Pool. """
        if self._result_already_returned():
            self.logger.log("error: result is already returned", min_level=1)
        self.deferred.errback(error)
        # self.deferred = None

    def _result_already_returned(self):
        """ Return True if an error or a result is already returned to Pool """
        return self.deferred.called

    def set_custom_headers(self, headers):
        """
        Set custom HTTP headers to be sent with each request. Passed headers
        are merged with QWebKit default headers, overwriting QWebKit values
        in case of conflicts.
        """
        self.web_page.custom_headers = headers

    def set_images_enabled(self, enabled):
        self.web_page.settings().setAttribute(QWebSettings.AutoLoadImages, enabled)

    def set_viewport(self, size):
        """
        Set viewport size.
        If size is "full" viewport size is detected automatically.
        If can also be "<width>x<height>".
        """
        if size == 'full':
            size = self.web_page.mainFrame().contentsSize()
            if size.isEmpty():
                self.logger.log("contentsSize method doesn't work %s", min_level=1)
                size = defaults.VIEWPORT_FALLBACK

        if not isinstance(size, QSize):
            w, h = map(int, size.split('x'))
            size = QSize(w, h)

        self.web_page.setViewportSize(size)
        w, h = int(size.width()), int(size.height())
        self.logger.log("viewport size is set to %sx%s" % (w, h), min_level=2)
        return w, h

    def lock_navigation(self):
        self.web_page.navigation_locked = True

    def unlock_navigation(self):
        self.web_page.navigation_locked = False

    def set_content(self, data, callback, errback, mime_type=None, baseurl=None):
        """
        Set page contents to ``data``, then wait until page loads.
        Invoke a callback if load was successful or errback if it wasn't.
        """
        if mime_type is None:
            mime_type = "text/html; charset=utf-8"
        if baseurl is None:
            baseurl = ''
        if isinstance(data, unicode):
            data = data.encode('utf8')
        callback_id = self._load_finished.connect(
            self._on_content_ready,
            callback=callback,
            errback=errback,
        )
        self.logger.log("callback %s is connected to loadFinished" % callback_id, min_level=3)
        self.web_page.mainFrame().setContent(data, mime_type, QUrl(baseurl))

    def set_user_agent(self, value):
        """ Set User-Agent header for future requests """
        self.http_client.set_user_agent(value)

    def get_cookies(self):
        """ Return a list of all cookies in the current cookiejar """
        return cookies2har(self.web_page.cookiejar.allCookies())

    def init_cookies(self, cookies):
        """ Replace all current cookies with ``cookies`` """
        self.web_page.cookiejar.init(cookies)

    def clear_cookies(self):
        """ Remove all cookies. Return a number of cookies deleted. """
        return self.web_page.cookiejar.clear()

    def delete_cookies(self, name=None, url=None):
        """
        Delete cookies with name == ``name``.

        If ``url`` is not None then only those cookies are deleted wihch
        are to be added when a request is sent to ``url``.

        Return a number of cookies deleted.
        """
        return self.web_page.cookiejar.delete(name, url)

    def add_cookie(self, cookie):
        return self.web_page.cookiejar.add(cookie)

    @property
    def url(self):
        """ Current URL """
        return unicode(self.web_page.mainFrame().url().toString())

    def go(self, url, callback, errback, baseurl=None, http_method='GET',
           body=None, headers=None):
        """
        Go to an URL. This is similar to entering an URL in
        address tab and pressing Enter.
        """
        self.store_har_timing("_onStarted")

        if baseurl:
            # If baseurl is used, we download the page manually,
            # then set its contents to the QWebPage and let it
            # download related resources and render the result.
            cb = functools.partial(
                self._on_baseurl_request_finished,
                callback=callback,
                errback=errback,
                baseurl=baseurl,
                url=url,
            )
            self.http_client.request(url,
                callback=cb,
                method=http_method,
                body=body,
                headers=headers,
                follow_redirects=True,
            )
        else:
            # if not self._goto_callbacks.isempty():
            #     self.logger.log("Only a single concurrent 'go' request is supported. "
            #                     "Previous go requests will be cancelled.", min_level=1)
            #     # When a new URL is loaded to mainFrame an errback will
            #     # be called, so we're not cancelling this callback manually.

            callback_id = self._load_finished.connect(
                self._on_content_ready,
                callback=callback,
                errback=errback,
            )
            self.logger.log("callback %s is connected to loadFinished" % callback_id, min_level=3)
            self._load_url_to_mainframe(url, http_method, body, headers=headers)

    def stop_loading(self):
        """
        Stop loading of the current page and all pending page
        refresh/redirect requests.
        """
        self.logger.log("stop_loading", min_level=2)
        self.web_view.pageAction(QWebPage.StopScheduledPageRefresh)
        self.web_view.stop()

    def close(self):
        """ Destroy this tab """
        self._closing = True
        self.web_view.pageAction(QWebPage.StopScheduledPageRefresh)
        self.web_view.stop()
        self.web_view.close()
        self.web_page.deleteLater()
        self.web_view.deleteLater()
        self._cancel_all_timers()

    @skip_if_closing
    def _on_load_finished(self, ok):
        if self.web_page.maybe_redirect(ok):
            self.logger.log("Redirect or other non-fatal error detected", min_level=2)
            return

        if self.web_page.is_ok(ok):  # or maybe_redirect:
            self.logger.log("loadFinished: ok", min_level=2)
        else:
            self._cancel_timers(self._timers_to_cancel_on_error)

            if self.web_page.error_loading(ok):
                self.logger.log("loadFinished: %s" % (str(self.web_page.error_info)), min_level=1)
            else:
                self.logger.log("loadFinished: unknown error", min_level=1)

    def _on_baseurl_request_finished(self, callback, errback, baseurl, url):
        """
        This method is called when ``baseurl`` is used and a
        reply for the first request is received.
        """
        self.logger.log("baseurl_request_finished", min_level=2)
        reply = self.sender()
        mime_type = reply.header(QNetworkRequest.ContentTypeHeader).toString()
        data = reply.readAll()
        self.set_content(
            data=data,
            callback=callback,
            errback=errback,
            mime_type=mime_type,
            baseurl=baseurl,
        )
        if reply.error():
            self.logger.log("Error loading %s: %s" % (url, reply.errorString()), min_level=1)

    def _load_url_to_mainframe(self, url, http_method, body=None, headers=None):
        request = self.http_client.request_obj(url, headers=headers)
        meth = OPERATION_QT_CONSTANTS[http_method]
        if body is None:  # PyQT doesn't support body=None
            self.web_page.mainFrame().load(request, meth)
        else:
            self.web_page.mainFrame().load(request, meth, body)

    @skip_if_closing
    def _on_content_ready(self, ok, callback, errback, callback_id):
        """
        This method is called when a QWebPage finishes loading its contents.
        """
        if self.web_page.maybe_redirect(ok):
            # XXX: It assumes loadFinished will be called again because
            # redirect happens. If redirect is detected improperly,
            # loadFinished won't be called again, and Splash will return
            # the result only after a timeout.
            return

        self.logger.log("loadFinished: disconnecting callback %s" % callback_id, min_level=3)
        self._load_finished.disconnect(callback_id)

        if self.web_page.is_ok(ok):
            callback()
        elif self.web_page.error_loading(ok):
            # XXX: maybe return a meaningful error page instead of generic
            # error message?
            errback()
            # errback(RenderError())
        else:
            errback()
            # errback(RenderError())

    def wait(self, time_ms, callback, onredirect=None, onerror=None):
        """
        Wait for time_ms, then run callback.

        If onredirect is True then the timer is cancelled if redirect happens.
        If onredirect is callable then in case of redirect the timer is
        cancelled and this callable is called.

        If onerror is True then the timer is cancelled if a render error
        happens. If onerror is callable then in case of a render error the
        timer is cancelled and this callable is called.
        """

        timer = QTimer()
        timer.setSingleShot(True)
        timer_callback = functools.partial(self._on_wait_timeout,
            timer=timer,
            callback=callback,
        )
        timer.timeout.connect(timer_callback)

        self.logger.log("waiting %sms; timer %s" % (time_ms, id(timer)), min_level=2)

        timer.start(time_ms)
        self._active_timers.add(timer)
        if onredirect:
            self._timers_to_cancel_on_redirect[timer] = onredirect
        if onerror:
            self._timers_to_cancel_on_error[timer] = onerror

    def _on_wait_timeout(self, timer, callback):
        self.logger.log("wait timeout for %s" % id(timer), min_level=2)
        if timer in self._active_timers:
            self._active_timers.remove(timer)
        self._timers_to_cancel_on_redirect.pop(timer, None)
        self._timers_to_cancel_on_error.pop(timer, None)
        callback()

    def _cancel_timer(self, timer, errback=None):
        self.logger.log("cancelling timer %s" % id(timer), min_level=2)
        if timer in self._active_timers:
            self._active_timers.remove(timer)
        timer.stop()
        try:
            if callable(errback):
                self.logger.log("calling timer errback", min_level=2)
                errback()
        finally:
            timer.deleteLater()

    def _cancel_timers(self, timers):
        for timer, oncancel in list(timers.items()):
            self._cancel_timer(timer, oncancel)
            timers.pop(timer, None)

    def _cancel_all_timers(self):
        self.logger.log("cancelling %d remaining timers" % len(self._active_timers), min_level=2)
        for timer in list(self._active_timers):
            self._cancel_timer(timer)

    def _on_url_changed(self, url):
        # log history
        url = unicode(url.toString())
        cause_ev = self.web_page.har_log._prev_entry(url, -1)
        if cause_ev:
            self._history.append(without_private(cause_ev.data))

        self._cancel_timers(self._timers_to_cancel_on_redirect)

    def run_js_file(self, filename):
        """
        Load JS library from file ``filename`` to the current frame.
        """
        with open(filename, 'rb') as f:
            script = f.read().decode('utf-8')
            return self.runjs(script)

    def run_js_files(self, folder):
        """
        Load all JS libraries from ``folder`` folder to the current frame.
        """
        for jsfile in os.listdir(folder):
            if jsfile.endswith('.js'):
                filename = os.path.join(folder, jsfile)
                self.run_js_file(filename)

    def autoload(self, js_source):
        """ Execute JS code before each page load """
        self._autoload_scripts.append(js_source)

    def no_autoload(self):
        """ Remove all scripts scheduled for auto-loading """
        self._autoload_scripts = []

    def _on_javascript_window_object_cleared(self):
        for script in self._autoload_scripts:
            self.web_page.mainFrame().evaluateJavaScript(script)

    def http_get(self, url, callback, headers=None, follow_redirects=True):
        """ Send a GET request; call a callback with the reply as an argument. """
        self.http_client.get(url,
            callback=callback,
            headers=headers,
            follow_redirects=follow_redirects
        )

    def runjs(self, js_source):
        """
        Run JS code in page context and return the result.
        Only string results are supported.
        """
        frame = self.web_page.mainFrame()
        res = frame.evaluateJavaScript(js_source)
        return qt2py(res)

    def store_har_timing(self, name):
        self.web_page.har_log.store_timing(name)

    def _jsconsole_enable(self):
        # TODO: add public interface or make console available by default
        if self._js_console is not None:
            return
        self._js_console = _JavascriptConsole()
        frame = self.web_page.mainFrame()
        frame.addToJavaScriptWindowObject('console', self._js_console)

    def _jsconsole_messages(self):
        # TODO: add public interface or make console available by default
        if self._js_console is None:
            return []
        return self._js_console.messages[:]

    def html(self):
        """ Return HTML of the current main frame """
        self.logger.log("getting HTML", min_level=2)
        frame = self.web_page.mainFrame()
        result = bytes(frame.toHtml().toUtf8())
        self.store_har_timing("_onHtmlRendered")
        return result

    def png(self, width=None, height=None, b64=False):
        """ Return screenshot in PNG format """
        self.logger.log("getting PNG", min_level=2)

        image = QImage(self.web_page.viewportSize(), QImage.Format_ARGB32)
        painter = QPainter(image)
        self.web_page.mainFrame().render(painter)
        painter.end()
        self.store_har_timing("_onScreenshotPrepared")

        if width:
            image = image.scaledToWidth(width, Qt.SmoothTransformation)
        if height:
            image = image.copy(0, 0, width, height)
        b = QBuffer()
        image.save(b, "png")
        result = bytes(b.data())
        if b64:
            result = base64.b64encode(result)
        self.store_har_timing("_onPngRendered")
        return result

    def iframes_info(self, children=True, html=True):
        """ Return information about all iframes """
        self.logger.log("getting iframes", min_level=3)
        frame = self.web_page.mainFrame()
        result = self._frame_to_dict(frame, children, html)
        self.store_har_timing("_onIframesRendered")
        return result

    def har(self):
        """ Return HAR information """
        self.logger.log("getting HAR", min_level=3)
        return self.web_page.har_log.todict()

    def history(self):
        """ Return history of 'main' HTTP requests """
        self.logger.log("getting history", min_level=3)
        return copy.deepcopy(self._history)

    def last_http_status(self):
        """
        Return HTTP status code of the currently loaded webpage
        or None if it is not available.
        """
        if not self._history:
            return
        try:
            return self._history[-1]["response"]["status"]
        except KeyError:
            return

    def _frame_to_dict(self, frame, children=True, html=True):
        g = frame.geometry()
        res = {
            "url": unicode(frame.url().toString()),
            "requestedUrl": unicode(frame.requestedUrl().toString()),
            "geometry": (g.x(), g.y(), g.width(), g.height()),
            "title": unicode(frame.title())
        }
        if html:
            res["html"] = unicode(frame.toHtml())

        if children:
            res["childFrames"] = [
                self._frame_to_dict(f, True, html)
                for f in frame.childFrames()
            ]
            res["frameName"] = unicode(frame.frameName())

        return res


class _SplashHttpClient(QObject):
    """ Wrapper class for making HTTP requests on behalf of a SplashQWebPage """
    def __init__(self, web_page):
        super(_SplashHttpClient, self).__init__()
        self._replies = set()
        self.web_page = web_page
        self.network_manager = web_page.networkAccessManager()

    def set_user_agent(self, value):
        """ Set User-Agent header for future requests """
        self.web_page.custom_user_agent = value

    def request_obj(self, url, headers=None):
        """ Return a QNetworkRequest object """
        request = QNetworkRequest()
        request.setUrl(QUrl(url))
        request.setOriginatingObject(self.web_page.mainFrame())

        if headers is not None:
            self.web_page.skip_custom_headers = True
            self._set_request_headers(request, headers)

        return request

    def request(self, url, callback, method='GET', body=None,
                headers=None, follow_redirects=True, max_redirects=5):
        """
        Create a request and return a QNetworkReply object with callback
        connected.
        """
        cb = functools.partial(
            self._on_request_finished,
            callback=callback,
            method=method,
            body=body,
            headers=headers,
            follow_redirects=follow_redirects,
            redirects_remaining=max_redirects,
        )
        return self._send_request(url, cb, method=method, body=body, headers=headers)

    def get(self, url, callback, headers=None, follow_redirects=True):
        """ Send a GET HTTP request; call the callback with the reply. """
        cb = functools.partial(
            self._on_get_finished,
            callback=callback,
            url=url,
        )
        self.request(url, cb, headers=headers, follow_redirects=follow_redirects)

    def _send_request(self, url, callback, method='GET', body=None,
                      headers=None):
        # XXX: The caller must ensure self._delete_reply is called in a callback.
        if method != 'GET':
            raise NotImplementedError()
        request = self.request_obj(url, headers=headers)
        reply = self.network_manager.get(request)
        reply.finished.connect(callback)
        self._replies.add(reply)
        return reply

    def _on_request_finished(self, callback, method, body, headers,
                             follow_redirects, redirects_remaining):
        """ Handle redirects and call the callback. """
        reply = self.sender()
        try:
            if not follow_redirects:
                callback()
                return
            if not redirects_remaining:
                callback()  # XXX: should it be an error?
                return

            redirect_url = reply.attribute(QNetworkRequest.RedirectionTargetAttribute).toPyObject()
            if redirect_url is None:  # no redirect
                callback()
                return

            redirect_url = reply.url().resolved(redirect_url)
            self.request(
                url=redirect_url,
                callback=callback,
                method=method,
                body=body,
                headers=headers,
                follow_redirects=follow_redirects,
                max_redirects=redirects_remaining-1,
            )
        finally:
            self._delete_reply(reply)

    def _on_get_finished(self, callback, url):
        reply = self.sender()
        callback(reply)

    def _set_request_headers(self, request, headers):
        """ Set HTTP headers for the request. """
        if isinstance(headers, dict):
            headers = headers.items()

        for name, value in headers or []:
            request.setRawHeader(name, value)
            if name.lower() == 'user-agent':
                self.set_user_agent(value)

    def _delete_reply(self, reply):
        self._replies.remove(reply)
        reply.close()
        reply.deleteLater()


class _JavascriptConsole(QObject):
    def __init__(self, parent=None):
        self.messages = []
        super(_JavascriptConsole, self).__init__(parent)

    @pyqtSlot(str)
    def log(self, message):
        self.messages.append(unicode(message))


class _BrowserTabLogger(object):
    """ This class logs various events that happen with QWebPage """
    def __init__(self, uid, web_page, verbosity):
        self.uid = uid
        self.web_page = web_page
        self.verbosity = verbosity

    def enable(self):
        # setup logging
        if self.verbosity >= 4:
            self.web_page.loadStarted.connect(self.on_load_started)
            self.web_page.mainFrame().loadFinished.connect(self.on_frame_load_finished)
            self.web_page.mainFrame().loadStarted.connect(self.on_frame_load_started)
            self.web_page.mainFrame().contentsSizeChanged.connect(self.on_contents_size_changed)
            # TODO: on_repaint

        if self.verbosity >= 3:
            self.web_page.mainFrame().javaScriptWindowObjectCleared.connect(self.on_javascript_window_object_cleared)
            self.web_page.mainFrame().initialLayoutCompleted.connect(self.on_initial_layout_completed)
            self.web_page.mainFrame().urlChanged.connect(self.on_url_changed)

    def on_load_started(self):
        self.log("loadStarted")

    def on_frame_load_finished(self, ok):
        self.log("mainFrame().LoadFinished %s" % ok)

    def on_frame_load_started(self):
        self.log("mainFrame().loadStarted")

    def on_contents_size_changed(self):
        self.log("mainFrame().contentsSizeChanged")

    def on_javascript_window_object_cleared(self):
        self.log("mainFrame().javaScriptWindowObjectCleared")

    def on_initial_layout_completed(self):
        self.log("mainFrame().initialLayoutCompleted")

    def on_url_changed(self, url):
        self.log("mainFrame().urlChanged %s" % qurl2ascii(url))

    def log(self, message, min_level=None):
        if min_level is not None and self.verbosity < min_level:
            return

        if isinstance(message, unicode):
            message = message.encode('unicode-escape').decode('ascii')

        message = "[%s] %s" % (self.uid, message)
        log.msg(message, system='render')

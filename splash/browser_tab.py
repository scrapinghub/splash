# -*- coding: utf-8 -*-
from __future__ import absolute_import
import base64
import functools
import os
import weakref
import uuid

from PyQt5.QtCore import QObject, QSize, Qt, QTimer, pyqtSlot, QEvent, QPointF
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWebKitWidgets import QWebPage
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWidgets import QApplication

from twisted.internet import defer
from twisted.python import log
import six

from splash import defaults
from splash.har.qt import cookies2har
from splash.network_manager import SplashQNetworkAccessManager
from splash.qtrender_image import QtImageRenderer
from splash.qtutils import (OPERATION_QT_CONSTANTS, WrappedSignal, qt2py,
                            qurl2ascii, to_qurl, qt_send_key, qt_send_text)
from splash.render_options import validate_size_str
from splash.qwebpage import SplashQWebPage, SplashQWebView
from splash.exceptions import JsError, OneShotCallbackError, ScriptError
from splash.utils import to_bytes
from splash.jsutils import (
    get_sanitized_result_js,
    SANITIZE_FUNC_JS,
    get_process_errors_js,
    escape_js,
)


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

    XXX: are cookies shared between "browser tabs"? In real browsers they are,
    but maybe this is not what we want.
    """

    def __init__(self, network_manager, splash_proxy_factory, verbosity,
                 render_options, visible=False):
        """ Create a new browser tab. """
        QObject.__init__(self)
        self.deferred = defer.Deferred()
        self.network_manager = network_manager
        self.verbosity = verbosity
        self.visible = visible
        self._uid = render_options.get_uid()
        self._closing = False
        self._closing_normally = False
        self._active_timers = set()
        self._timers_to_cancel_on_redirect = weakref.WeakKeyDictionary()  # timer: callback
        self._timers_to_cancel_on_error = weakref.WeakKeyDictionary()  # timer: callback
        self._callback_proxies_to_cancel = weakref.WeakSet()
        self._js_console = None
        self._autoload_scripts = []

        self.logger = _BrowserTabLogger(uid=self._uid, verbosity=verbosity)
        self._init_webpage(verbosity, network_manager, splash_proxy_factory,
                           render_options)
        self.http_client = _SplashHttpClient(self.web_page)

    def _init_webpage(self, verbosity, network_manager, splash_proxy_factory, render_options):
        """ Create and initialize QWebPage and QWebView """
        self.web_page = SplashQWebPage(verbosity)
        self.web_page.setNetworkAccessManager(network_manager)
        self.web_page.splash_proxy_factory = splash_proxy_factory
        self.web_page.render_options = render_options

        self._set_default_webpage_options(self.web_page)
        self._setup_webpage_events()

        self.web_view = SplashQWebView()
        self.web_view.setPage(self.web_page)
        self.web_view.setAttribute(Qt.WA_DeleteOnClose, True)
        self.web_view.onBeforeClose = self._on_before_close

        if self.visible:
            self.web_view.move(0, 0)
            self.web_view.show()

        self.set_viewport(defaults.VIEWPORT_SIZE)
        # XXX: hack to ensure that default window size is not 640x480.
        self.web_view.resize(
            QSize(*map(int, defaults.VIEWPORT_SIZE.split('x'))))

    def set_js_enabled(self, val):
        settings = self.web_page.settings()
        settings.setAttribute(QWebSettings.JavascriptEnabled, val)

    def get_js_enabled(self):
        settings = self.web_page.settings()
        return settings.testAttribute(QWebSettings.JavascriptEnabled)

    def set_private_mode_enabled(self, val):
        settings = self.web_page.settings()
        settings.setAttribute(QWebSettings.PrivateBrowsingEnabled, bool(val))
        settings.setAttribute(QWebSettings.LocalStorageEnabled, not bool(val))

    def get_private_mode_enabled(self):
        settings = self.web_page.settings()
        return settings.testAttribute(QWebSettings.PrivateBrowsingEnabled)

    def get_response_body_enabled(self):
        return self.web_page.response_body_enabled

    def set_response_body_enabled(self, val):
        self.web_page.response_body_enabled = val

    def _set_default_webpage_options(self, web_page):
        """
        Set QWebPage options.
        TODO: allow to customize them.
        """
        settings = web_page.settings()
        settings.setAttribute(QWebSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebSettings.LocalContentCanAccessRemoteUrls, True)

        scroll_bars = Qt.ScrollBarAsNeeded if self.visible else Qt.ScrollBarAlwaysOff
        web_page.mainFrame().setScrollBarPolicy(Qt.Vertical, scroll_bars)
        web_page.mainFrame().setScrollBarPolicy(Qt.Horizontal, scroll_bars)

        if self.visible:
            web_page.settings().setAttribute(QWebSettings.DeveloperExtrasEnabled, True)

        self.set_plugins_enabled(defaults.PLUGINS_ENABLED)
        self.set_response_body_enabled(defaults.RESPONSE_BODY_ENABLED)

    def _setup_webpage_events(self):
        self._load_finished = WrappedSignal(self.web_page.mainFrame().loadFinished)
        self.web_page.mainFrame().loadFinished.connect(self._on_load_finished)
        self.web_page.mainFrame().urlChanged.connect(self._on_url_changed)
        self.web_page.mainFrame().javaScriptWindowObjectCleared.connect(self._on_javascript_window_object_cleared)
        self.logger.add_web_page(self.web_page)

    def return_result(self, result):
        """ Return a result to the Pool. """
        if self._result_already_returned():
            self.logger.log("error: result is already returned", min_level=1)

        self.deferred.callback(result)
        # self.deferred = None

    def return_error(self, error):
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

    def set_resource_timeout(self, timeout):
        """ Set a default timeout for HTTP requests, in seconds. """
        self.web_page.resource_timeout = timeout

    def get_resource_timeout(self):
        """ Get a default timeout for HTTP requests, in seconds. """
        return self.web_page.resource_timeout

    def set_images_enabled(self, enabled):
        self.web_page.settings().setAttribute(QWebSettings.AutoLoadImages,
                                              enabled)

    def get_images_enabled(self):
        settings = self.web_page.settings()
        return settings.testAttribute(QWebSettings.AutoLoadImages)

    def set_plugins_enabled(self, enabled):
        self.web_page.settings().setAttribute(QWebSettings.PluginsEnabled,
                                              bool(enabled))

    def get_plugins_enabled(self):
        settings = self.web_page.settings()
        return bool(settings.testAttribute(QWebSettings.PluginsEnabled))

    def set_viewport(self, size, raise_if_empty=False):
        """
        Set viewport size.
        If size is "full" viewport size is detected automatically.
        If can also be "<width>x<height>".

        .. note::

           This will update all JS geometry variables, but window resize event
           is delivered asynchronously and so ``window.resize`` will not be
           invoked until control is yielded to the event loop.

        """
        if size == 'full':
            size = self.web_page.mainFrame().contentsSize()
            self.logger.log("Contents size: %s" % size, min_level=2)
            if size.isEmpty():
                if raise_if_empty:
                    raise RuntimeError("Cannot detect viewport size")
                else:
                    size = defaults.VIEWPORT_SIZE
                    self.logger.log("Viewport is empty, falling back to: %s" %
                                    size)

        if not isinstance(size, QSize):
            validate_size_str(size)
            w, h = map(int, size.split('x'))
            size = QSize(w, h)
        self.web_page.setViewportSize(size)
        self._force_relayout()
        w, h = int(size.width()), int(size.height())
        self.logger.log("viewport size is set to %sx%s" % (w, h), min_level=2)
        return w, h

    def _force_relayout(self):
        """Force a relayout of the web page contents."""
        # setPreferredContentsSize may be used to force a certain size for
        # layout purposes.  Passing an invalid size resets the override and
        # tells the QWebPage to use the size as requested by the document.
        # This is in fact the default behavior, so we don't change anything.
        #
        # The side-effect of this operation is a forced synchronous relayout of
        # the page.
        self.web_page.setPreferredContentsSize(QSize())

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
        callback_id = self._load_finished.connect(
            self._on_content_ready,
            callback=callback,
            errback=errback,
        )
        self.logger.log("callback %s is connected to loadFinished" % callback_id, min_level=3)
        self.web_page.mainFrame().setContent(data, mime_type, to_qurl(baseurl))

    def set_user_agent(self, value):
        """ Set User-Agent header for future requests """
        if isinstance(value, bytes):
            value = value.decode("utf8")
        self.http_client.set_user_agent(value)

    def get_cookies(self):
        """ Return a list of all cookies in the current cookiejar """
        return cookies2har(self.network_manager.cookiejar.allCookies())

    def init_cookies(self, cookies):
        """ Replace all current cookies with ``cookies`` """
        self.network_manager.cookiejar.init(cookies)

    def clear_cookies(self):
        """ Remove all cookies. Return a number of cookies deleted. """
        return self.network_manager.cookiejar.clear()

    def delete_cookies(self, name=None, url=None):
        """
        Delete cookies with name == ``name``.

        If ``url`` is not None then only those cookies are deleted wihch
        are to be added when a request is sent to ``url``.

        Return a number of cookies deleted.
        """
        return self.network_manager.cookiejar.delete(name, url)

    def add_cookie(self, cookie):
        return self.network_manager.cookiejar.add(cookie)

    @property
    def url(self):
        """ Current URL """
        return six.text_type(self.web_page.mainFrame().url().toString())

    def go(self, url, callback, errback, baseurl=None, http_method='GET',
           body=None, headers=None):
        """
        Go to an URL. This is similar to entering an URL in
        address tab and pressing Enter.
        """
        self.store_har_timing("_onStarted")

        if body is not None:
            body = to_bytes(body)

        headers_user_agent = _get_header_value(headers, b"user-agent")
        if headers_user_agent:
            # User passed User-Agent header to go() so we need to set
            # consistent UA for all rendering requests.
            # Passing UA header to go() will have same effect as splash:set_user_agent().
            self.set_user_agent(headers_user_agent)

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

    def register_callback(self, event, callback):
        """ Register a callback for an event """
        self.web_page.callbacks[event].append(callback)

    def clear_callbacks(self, event=None):
        self.web_page.clear_callbacks(event)

    # def remove_callback(self, event, callback):
    #     """ Unregister a callback for an event """
    #     self.web_page.callbacks[event].remove(callback)

    @skip_if_closing
    def close(self):
        """ Destroy this tab """
        self.logger.log("close is requested by a script", min_level=2)
        self._closing = True
        self._closing_normally = True
        self.web_view.pageAction(QWebPage.StopScheduledPageRefresh)
        self.web_view.stop()
        self.web_view.close()
        self.web_page.deleteLater()
        self.web_view.deleteLater()
        self.network_manager.deleteLater()
        self.clear_callbacks()
        self._cancel_all_timers()

    def _on_before_close(self):
        # self._closing = True
        # self._cancel_all_timers()
        # if not self._closing_normally:
        #     self.return_error(Exception("Window is closed by user"))
        return True  # don't close the window

    @skip_if_closing
    def _on_load_finished(self, ok):
        """
        This callback is called for all web_page.mainFrame()
        loadFinished events.
        """
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
        mime_type = reply.header(QNetworkRequest.ContentTypeHeader)
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
        request = self.http_client.request_obj(url, headers=headers, body=body)
        meth = OPERATION_QT_CONSTANTS[http_method]
        if body is None:  # PyQT doesn't support body=None
            self.web_page.mainFrame().load(request, meth)
        else:
            assert isinstance(body, bytes)
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
            errback(self.web_page.error_info)
        else:
            # XXX: it means ok=False. When does it happen?
            errback(self.web_page.error_info)

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
        try:
            timer.stop()
            if callable(errback):
                self.logger.log("calling timer errback", min_level=2)
                errback(self.web_page.error_info)
        finally:
            timer.deleteLater()

    def _cancel_timers(self, timers):
        for timer, oncancel in list(timers.items()):
            self._cancel_timer(timer, oncancel)
            timers.pop(timer, None)

    def _cancel_all_timers(self):
        total_len = len(self._active_timers) + len(self._callback_proxies_to_cancel)
        self.logger.log("cancelling %d remaining timers" % total_len, min_level=2)
        for timer in list(self._active_timers):
            self._cancel_timer(timer)
        for callback_proxy in self._callback_proxies_to_cancel:
            callback_proxy.use_up()

    def _on_url_changed(self, url):
        self.web_page.har.store_redirect(six.text_type(url.toString()))
        self._cancel_timers(self._timers_to_cancel_on_redirect)

    def run_js_file(self, filename, handle_errors=True):
        """
        Load JS library from file ``filename`` to the current frame.
        """
        with open(filename, 'rb') as f:
            script = f.read().decode('utf-8')
            self.runjs(script, handle_errors=handle_errors)

    def run_js_files(self, folder, handle_errors=True):
        """
        Load all JS libraries from ``folder`` folder to the current frame.
        """
        for jsfile in os.listdir(folder):
            if jsfile.endswith('.js'):
                filename = os.path.join(folder, jsfile)
                self.run_js_file(filename, handle_errors=handle_errors)

    def autoload(self, js_source):
        """ Execute JS code before each page load """
        self._autoload_scripts.append(js_source)

    def autoload_reset(self):
        """ Remove all scripts scheduled for auto-loading """
        self._autoload_scripts = []

    def _on_javascript_window_object_cleared(self):
        for script in self._autoload_scripts:
            # XXX: handle_errors=False is used to execute autoload scripts
            # in a global context (not inside a closure).
            # One difference is how are `function foo(){}` statements handled:
            # if executed globally, `foo` becomes an attribute of window;
            # if executed in a closure, `foo` is a name local to this closure.
            self.runjs(script, handle_errors=False)

    def http_get(self, url, callback, headers=None, follow_redirects=True):
        """ Send a GET request; call a callback with the reply as an argument. """
        self.http_client.get(url,
            callback=callback,
            headers=headers,
            follow_redirects=follow_redirects
        )

    def http_post(self, url, callback, headers=None, follow_redirects=True, body=None):
        if body is not None:
            body = to_bytes(body)

        self.http_client.post(url,
                              callback=callback,
                              headers=headers,
                              follow_redirects=follow_redirects,
                              body=body)

    def evaljs(self, js_source, handle_errors=True, result_protection=True):
        """
        Run JS code in page context and return the result.

        If JavaScript exception or an syntax error happens
        and `handle_errors` is True then Python JsError
        exception is raised.

        When `result_protection` is True (default) protection against
        badly written or malicious scripts is activated. Disable it
        when the script result is known to be good, i.e. it only
        contains objects/arrays/primitives without circular references.
        """
        frame = self.web_page.mainFrame()
        eval_expr = u"eval({})".format(escape_js(js_source))

        if result_protection:
            eval_expr = get_sanitized_result_js(eval_expr)

        if not handle_errors:
            return qt2py(frame.evaluateJavaScript(eval_expr))

        res = frame.evaluateJavaScript(get_process_errors_js(eval_expr))

        if not isinstance(res, dict):
            raise JsError({
                'type': ScriptError.UNKNOWN_ERROR,
                'js_error_message': res,
                'message': "unknown JS error: {!r}".format(res)
            })

        if res.get("error", False):
            err_message = res.get('errorMessage')
            err_type = res.get('errorType', '<custom JS error>')
            err_repr = res.get('errorRepr', '<unknown JS error>')
            if err_message is None:
                err_message = err_repr
            raise JsError({
                'type': ScriptError.JS_ERROR,
                'js_error_type': err_type,
                'js_error_message': err_message,
                'js_error': err_repr,
                'message': "JS error: {!r}".format(err_repr)
            })

        return res.get("result", None)

    def runjs(self, js_source, handle_errors=True):
        """ Run JS code in page context and discard the result. """

        # If JS code returns something, and we just discard
        # the result of frame.evaluateJavaScript, then Qt still needs to build
        # a result - it could be costly. So the original JS code
        # is adjusted to make sure it doesn't return anything.
        self.evaljs(
            js_source="%s;undefined" % js_source,
            handle_errors=handle_errors,
            result_protection=False
        )

    def wait_for_resume(self, js_source, callback, errback, timeout):
        """
        Run some Javascript asynchronously.

        The JavaScript must contain a method called `main()` that accepts
        one argument. The first argument will be an object with `resume()`
        and `error()` methods. The code _must_ call one of these functions
        before the timeout or else it will be canceled.
        """

        frame = self.web_page.mainFrame()
        callback_proxy = OneShotCallbackProxy(self, callback, errback, timeout)
        self._callback_proxies_to_cancel.add(callback_proxy)
        frame.addToJavaScriptWindowObject(callback_proxy.name, callback_proxy)

        wrapped = u"""
        (function () {
            try {
                eval(%(script_text)s);
            } catch (err) {
                var main = function (splash) {
                    throw err;
                }
            }
            (function () {
                var sanitize = %(sanitize_func)s;
                var _result = {};
                var _splash = window["%(callback_name)s"];
                var splash = {
                    'error': function (message) {
                        _splash.error(message, false);
                    },
                    'resume': function (value) {
                        _result['value'] = value;
                        try {
                            _splash.resume(sanitize(_result));
                        } catch (err) {
                            _splash.error(err, true);
                        }
                    },
                    'set': function (key, value) {
                        _result[key] = value;
                    }
                };
                delete window["%(callback_name)s"];
                try {
                    if (typeof main === 'undefined') {
                        throw "wait_for_resume(): no main() function defined";
                    }
                    main(splash);
                } catch (err) {
                    _splash.error(err, true);
                }
            })();
        })();undefined
        """ % dict(
            sanitize_func=SANITIZE_FUNC_JS,
            script_text=escape_js(js_source),
            callback_name=callback_proxy.name
        )

        def cancel_callback():
            callback_proxy.cancel(reason='javascript window object cleared')

        self.logger.log("wait_for_resume wrapped script:\n%s" % wrapped,
                        min_level=3)
        frame.javaScriptWindowObjectCleared.connect(cancel_callback)
        frame.evaluateJavaScript(wrapped)

    def store_har_timing(self, name):
        self.logger.log("HAR event: %s" % name, min_level=3)
        self.web_page.har.store_timing(name)

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
        result = frame.toHtml()
        self.store_har_timing("_onHtmlRendered")
        return result

    def _get_image(self, image_format, width, height, render_all,
                   scale_method, region):
        old_size = self.web_page.viewportSize()
        try:
            if render_all:
                self.logger.log("Rendering whole page contents (RENDER_ALL)",
                                min_level=2)
                self.set_viewport('full')
            renderer = QtImageRenderer(
                self.web_page, self.logger, image_format,
                width=width, height=height, scale_method=scale_method,
                region=region)
            image = renderer.render_qwebpage()
        finally:
            if old_size != self.web_page.viewportSize():
                # Let's not generate extra "set size" messages in the log.
                self.web_page.setViewportSize(old_size)
        self.store_har_timing("_onScreenshotPrepared")
        return image

    def png(self, width=None, height=None, b64=False, render_all=False,
            scale_method=None, region=None):
        """ Return screenshot in PNG format """
        self.logger.log(
            "Getting PNG: width=%s, height=%s, "
            "render_all=%s, scale_method=%s, region=%s" %
            (width, height, render_all, scale_method, region), min_level=2)
        image = self._get_image('PNG', width, height, render_all,
                                scale_method, region=region)
        result = image.to_png()
        if b64:
            result = base64.b64encode(result).decode('utf-8')
        self.store_har_timing("_onPngRendered")
        return result

    def jpeg(self, width=None, height=None, b64=False, render_all=False,
             scale_method=None, quality=None, region=None):
        """ Return screenshot in JPEG format. """
        self.logger.log(
            "Getting JPEG: width=%s, height=%s, "
            "render_all=%s, scale_method=%s, quality=%s, region=%s" %
            (width, height, render_all, scale_method, quality, region),
            min_level=2)
        image = self._get_image('JPEG', width, height, render_all,
                                scale_method, region=region)
        result = image.to_jpeg(quality=quality)
        if b64:
            result = base64.b64encode(result).decode('utf-8')
        self.store_har_timing("_onJpegRendered")
        return result

    def iframes_info(self, children=True, html=True):
        """ Return information about all iframes """
        self.logger.log("getting iframes", min_level=3)
        frame = self.web_page.mainFrame()
        result = self._frame_to_dict(frame, children, html)
        self.store_har_timing("_onIframesRendered")
        return result

    def har(self, reset=False):
        """ Return HAR information """
        self.logger.log("getting HAR", min_level=3)
        res = self.web_page.har.todict()
        if reset:
            self.har_reset()
        return res

    def har_reset(self):
        """ Drop current HAR information """
        self.logger.log("HAR information is reset", min_level=3)
        return self.web_page.reset_har()

    def history(self):
        """ Return history of 'main' HTTP requests """
        self.logger.log("getting history", min_level=3)
        return self.web_page.har.get_history()

    def last_http_status(self):
        """
        Return HTTP status code of the currently loaded webpage
        or None if it is not available.
        """
        return self.web_page.har.get_last_http_status()

    def _frame_to_dict(self, frame, children=True, html=True):
        g = frame.geometry()
        res = {
            "url": six.text_type(frame.url().toString()),
            "requestedUrl": six.text_type(frame.requestedUrl().toString()),
            "geometry": (g.x(), g.y(), g.width(), g.height()),
            "title": six.text_type(frame.title())
        }
        if html:
            res["html"] = six.text_type(frame.toHtml())

        if children:
            res["childFrames"] = [
                self._frame_to_dict(f, True, html)
                for f in frame.childFrames()
            ]
            res["frameName"] = six.text_type(frame.frameName())

        return res

    def mouse_click(self, x, y, button="left"):
        """Clicks elements on webpage.

        :param x integer with X screen position to click
        :param y integer with Y screen position to click
        :param button string specifying button type
        :return: None
        """
        # XXX only left click supported for now, we can add support and tests for right click
        # in the future if there is need for that
        self.mouse_press(x, y, button)
        self.mouse_release(x, y, button)

    def mouse_press(self, x, y, button="left"):
        self._post_mouse_event(QEvent.MouseButtonPress, button, x, y)

    def mouse_release(self, x, y, button="left"):
        self._post_mouse_event(QEvent.MouseButtonRelease, button, x, y)

    def mouse_hover(self, end_x, end_y):
        self._post_mouse_event(QEvent.MouseMove, "nobutton", end_x, end_y)

    def _post_mouse_event(self, type, button, x, y):
        q_button = {
            # TODO perhaps add right button here
            "left": Qt.LeftButton,
            "nobutton": Qt.NoButton,
        }.get(button)
        point = QPointF(x, y)
        buttons = QApplication.mouseButtons()
        modifiers = QApplication.keyboardModifiers()
        event = QMouseEvent(type, point, q_button, buttons, modifiers)
        QApplication.postEvent(self.web_page, event)

    def send_text(self, text):
        """
        Send full text as input generated by a key event.
        :param text string to be sent as input
        :return: None
        """
        qt_send_text(text, self.web_page)

    def send_keys(self, text):
        """
        Send key events to webpage. Whitespace is used as a separator between
        key events.
        :param text string to be sent as key events
        :return: None
        """
        for key in text.split():
            qt_send_key(key, self.web_page)


class _SplashHttpClient(QObject):
    """ Wrapper class for making HTTP requests on behalf of a SplashQWebPage """
    def __init__(self, web_page):
        super(_SplashHttpClient, self).__init__()
        self._replies = set()
        self.web_page = web_page  # type: SplashQWebPage
        self.network_manager = web_page.networkAccessManager()  # type: SplashQNetworkAccessManager

    def set_user_agent(self, value):
        """ Set User-Agent header for future requests """
        self.web_page.custom_user_agent = value

    def request_obj(self, url, headers=None, body=None):
        """ Return a QNetworkRequest object """
        request = QNetworkRequest()
        request.setUrl(to_qurl(url))
        request.setOriginatingObject(self.web_page.mainFrame())

        if headers is not None:
            self.web_page.skip_custom_headers = True
            self._set_request_headers(request, headers)

        if body and not request.hasRawHeader(b"content-type"):
            # There is POST body but no content-type. QT will set this
            # header, but it will complain so better to do this here.
            request.setRawHeader(b"content-type",
                                 b"application/x-www-form-urlencoded")

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
        return self._send_request(url, cb, method=method, body=body,
                                  headers=headers)

    def get(self, url, callback, headers=None, follow_redirects=True):
        """ Send a GET HTTP request; call the callback with the reply. """
        cb = functools.partial(
            self._return_reply,
            callback=callback,
            url=url,
        )
        self.request(url, cb, headers=headers, follow_redirects=follow_redirects)

    def post(self, url, callback, headers=None, follow_redirects=True, body=None):
        """ Send HTTP POST request;
        """
        cb = functools.partial(self._return_reply, callback=callback, url=url)
        self.request(url, cb, headers=headers, follow_redirects=follow_redirects, body=body,
                     method="POST")

    def _send_request(self, url, callback, method='GET', body=None,
                      headers=None):
        # this is called when request is NOT downloaded via webpage.mainFrame()
        # XXX: The caller must ensure self._delete_reply is called in
        # a callback.
        if method.upper() not in ["POST", "GET"]:
            raise NotImplementedError()

        if body is not None:
            assert isinstance(body, bytes)

        request = self.request_obj(url, headers=headers, body=body)

        # setting UA for request that is not downloaded via
        # webpage.mainFrame().load_to_mainframe()
        ua_from_headers = _get_header_value(headers, b'user-agent')
        web_page_ua = self.web_page.userAgentForUrl(to_qurl(url))
        user_agent = ua_from_headers or web_page_ua
        request.setRawHeader(b"user-agent", to_bytes(user_agent))

        if method.upper() == "POST":
            reply = self.network_manager.post(request, body)
        else:
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

            redirect_url = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
            if redirect_url is None:  # no redirect
                callback()
                return

            # handle redirects after POST request
            if method.upper() == "POST":
                method = "GET"
                body = None

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

    def _return_reply(self, callback, url):
        reply = self.sender()
        callback(reply)

    def _set_request_headers(self, request, headers):
        """ Set HTTP headers for the request. """
        if isinstance(headers, dict):
            headers = headers.items()

        for name, value in headers or []:
            request.setRawHeader(to_bytes(name), to_bytes(value))

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
        self.messages.append(six.text_type(message))


class _BrowserTabLogger(object):
    """ This class logs various events that happen with QWebPage """
    def __init__(self, uid, verbosity):
        self.uid = uid
        self.verbosity = verbosity

    def add_web_page(self, web_page):
        frame = web_page.mainFrame()
        # setup logging
        if self.verbosity >= 4:
            web_page.loadStarted.connect(self.on_load_started)
            frame.loadFinished.connect(self.on_frame_load_finished)
            frame.loadStarted.connect(self.on_frame_load_started)
            frame.contentsSizeChanged.connect(self.on_contents_size_changed)
            # TODO: on_repaint

        if self.verbosity >= 3:
            frame.javaScriptWindowObjectCleared.connect(self.on_javascript_window_object_cleared)
            frame.initialLayoutCompleted.connect(self.on_initial_layout_completed)
            frame.urlChanged.connect(self.on_url_changed)

    def on_load_started(self):
        self.log("loadStarted")

    def on_frame_load_finished(self, ok):
        self.log("mainFrame().LoadFinished %s" % ok)

    def on_frame_load_started(self):
        self.log("mainFrame().loadStarted")

    @pyqtSlot('QSize')
    def on_contents_size_changed(self, sz):
        self.log("mainFrame().contentsSizeChanged: %s" % sz)

    def on_javascript_window_object_cleared(self):
        self.log("mainFrame().javaScriptWindowObjectCleared")

    def on_initial_layout_completed(self):
        self.log("mainFrame().initialLayoutCompleted")

    def on_url_changed(self, url):
        self.log("mainFrame().urlChanged %s" % qurl2ascii(url))

    def log(self, message, min_level=None):
        if min_level is not None and self.verbosity < min_level:
            return

        if isinstance(message, six.text_type):
            message = message.encode('unicode-escape').decode('ascii')

        message = "[%s] %s" % (self.uid, message)
        log.msg(message, system='render')


class OneShotCallbackProxy(QObject):
    """
    A proxy object that allows JavaScript to run Python callbacks.

    This creates a JavaScript-compatible object (can be added to `window`)
    that has functions `resume()` and `error()` that can be connected to
    Python callbacks.

    It is "one shot" because either `resume()` or `error()` should be called
    exactly _once_. It raises an exception if the combined number of calls
    to these methods is greater than 1.

    If timeout is zero, then the timeout is disabled.
    """

    def __init__(self, parent, callback, errback, timeout=0):
        self.name = str(uuid.uuid1())
        self._used_up = False
        self._callback = callback
        self._errback = errback

        if timeout < 0:
            raise ValueError('OneShotCallbackProxy timeout must be >= 0.')
        elif timeout == 0:
            self._timer = None
        elif timeout > 0:
            self._timer = QTimer()
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._timed_out)
            self._timer.start(timeout * 1000)

        super(OneShotCallbackProxy, self).__init__(parent)

    @pyqtSlot('QVariantMap')
    def resume(self, value=None):
        if self._used_up:
            raise OneShotCallbackError("resume() called on a one shot"
                                       " callback that was already used up.")

        self.use_up()
        self._callback(qt2py(value))

    @pyqtSlot(str, bool)
    def error(self, message, raise_=False):
        if self._used_up:
            raise OneShotCallbackError("error() called on a one shot"
                                       " callback that was already used up.")

        self.use_up()
        self._errback(message, raise_)

    def cancel(self, reason):
        self.use_up()
        self._errback("One shot callback canceled due to: %s." % reason,
                      raise_=False)

    def _timed_out(self):
        self.use_up()
        self._errback("One shot callback timed out while waiting for"
                      " resume() or error().", raise_=False)

    def use_up(self):
        self._used_up = True

        if self._timer is not None and self._timer.isActive():
            self._timer.stop()


def _get_header_value(headers, name, default=None):
    """ Return header value """
    if not headers:
        return default

    if isinstance(headers, dict):
        headers = headers.items()

    name = to_bytes(name.lower())
    for k, v in headers:
        if name == to_bytes(k.lower()):
            return v
    return default

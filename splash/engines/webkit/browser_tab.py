# -*- coding: utf-8 -*-
import base64
import functools
import os
import weakref
import traceback

from PyQt5.QtCore import (
    QObject, QSize, Qt, QTimer, pyqtSlot, QEvent,
    QPointF, QPoint, pyqtSignal,
)
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWebKitWidgets import QWebPage
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWidgets import QApplication

from splash import defaults
from splash.har.qt import cookies2har
from splash.qtutils import (
    OPERATION_QT_CONSTANTS,
    MediaSourceEnabled,
    MediaEnabled,
    WrappedSignal,
    qt2py,
    to_qurl,
    qt_send_key,
    qt_send_text,
    parse_size,
)
from splash.render_options import validate_size_str
from splash.errors import JsError, ScriptError
from splash.utils import to_bytes
from splash.jsutils import (
    get_sanitized_result_js,
    SANITIZE_FUNC_JS,
    get_process_errors_js,
    escape_js,
    store_dom_elements,
)
from splash.html_element import HTMLElement
from splash.browser_tab import (
    BrowserTab,
    OneShotCallbackProxy,
    skip_if_closing,
    webpage_option_getter,
    webpage_option_setter,
    webpage_attribute_getter,
    webpage_attribute_setter,
    EventsStorage,
    EventHandlersStorage,
    ElementsStorage,
)
from .http_client import SplashWebkitHttpClient, get_header_value
from .webpage import WebkitWebPage, WebkitEventLogger
from .webview import SplashQWebView
from .screenshot import QtWebkitScreenshotRenderer


class WebkitBrowserTab(BrowserTab):
    """
    An object for controlling a single browser tab (QWebView).

    It is created by splash.pool.Pool. Pool attaches to tab's deferred
    and waits until either a callback or an errback is called, then destroys
    a WebkitBrowserTab.

    XXX: are cookies shared between "browser tabs"? In real browsers they are,
    but maybe this is not what we want.
    """

    def __init__(self, render_options, verbosity,
                 network_manager, splash_proxy_factory,
                 visible=False):
        """ Create a new browser tab. """
        super().__init__(render_options, verbosity)
        self.network_manager = network_manager
        self.visible = visible
        self._closing_normally = False
        self._callback_proxies_to_cancel = weakref.WeakSet()
        self._js_console = None
        self._autoload_scripts = []
        self._js_storage_initiated = False
        self._init_webpage(verbosity, network_manager, splash_proxy_factory,
                           render_options)
        self.http_client = SplashWebkitHttpClient(self.web_page)

    def _init_webpage(self, verbosity, network_manager, splash_proxy_factory,
                      render_options):
        """ Create and initialize QWebPage and QWebView """
        self.web_page = WebkitWebPage(verbosity)
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
        self.web_view.resize(parse_size(defaults.VIEWPORT_SIZE))

    def _init_elements_storage(self):
        frame = self.web_page.mainFrame()
        self._elements_storage = ElementsStorage(self)
        frame.addToJavaScriptWindowObject(self._elements_storage.name,
                                          self._elements_storage)

    def _init_event_handlers_storage(self):
        frame = self.web_page.mainFrame()
        self._event_handlers_storage = EventHandlersStorage(self,
                                                            self._events_storage)
        frame.addToJavaScriptWindowObject(self._event_handlers_storage.name,
                                          self._event_handlers_storage)

    def _clear_event_handlers_storage(self):
        if hasattr(self, '_event_handlers_storage'):
            self._event_handlers_storage.clear()

    def _init_events_storage(self):
        frame = self.web_page.mainFrame()
        self._events_storage = EventsStorage(self)
        frame.addToJavaScriptWindowObject(self._events_storage.name,
                                          self._events_storage)
        self._events_storage.init_storage()

    def _init_js_objects_storage(self):
        if self._js_storage_initiated:
            return

        self._init_elements_storage()
        self._init_events_storage()
        self._init_event_handlers_storage()
        self._js_storage_initiated = True

    get_js_enabled = webpage_option_getter(QWebSettings.JavascriptEnabled)
    set_js_enabled = webpage_option_setter(QWebSettings.JavascriptEnabled)

    get_private_mode_enabled = webpage_option_getter(QWebSettings.PrivateBrowsingEnabled)
    def set_private_mode_enabled(self, val):
        settings = self.web_page.settings()
        settings.setAttribute(QWebSettings.PrivateBrowsingEnabled, bool(val))
        settings.setAttribute(QWebSettings.LocalStorageEnabled, not bool(val))

    get_images_enabled = webpage_option_getter(QWebSettings.AutoLoadImages)
    set_images_enabled = webpage_option_setter(QWebSettings.AutoLoadImages)

    get_plugins_enabled = webpage_option_getter(QWebSettings.PluginsEnabled)
    set_plugins_enabled = webpage_option_setter(QWebSettings.PluginsEnabled, bool)

    get_indexeddb_enabled = webpage_option_getter(QWebSettings.OfflineStorageDatabaseEnabled)
    set_indexeddb_enabled = webpage_option_setter(QWebSettings.OfflineStorageDatabaseEnabled)

    get_media_source_enabled = webpage_option_getter(MediaSourceEnabled)
    set_media_source_enabled = webpage_option_setter(MediaSourceEnabled)

    get_html5_media_enabled = webpage_option_getter(MediaEnabled)
    set_html5_media_enabled = webpage_option_setter(MediaEnabled)

    get_webgl_enabled = webpage_option_getter(QWebSettings.WebGLEnabled)
    set_webgl_enabled = webpage_option_setter(QWebSettings.WebGLEnabled)

    def _set_default_webpage_options(self, web_page):
        """ Set QWebPage options. TODO: allow to customize defaults. """
        settings = web_page.settings()
        settings.setAttribute(QWebSettings.LocalContentCanAccessRemoteUrls, True)

        scroll_bars = Qt.ScrollBarAsNeeded if self.visible else Qt.ScrollBarAlwaysOff
        web_page.mainFrame().setScrollBarPolicy(Qt.Vertical, scroll_bars)
        web_page.mainFrame().setScrollBarPolicy(Qt.Horizontal, scroll_bars)

        if self.visible:
            settings.setAttribute(QWebSettings.DeveloperExtrasEnabled, True)

        self.set_js_enabled(True)
        self.set_plugins_enabled(defaults.PLUGINS_ENABLED)
        self.set_request_body_enabled(defaults.REQUEST_BODY_ENABLED)
        self.set_response_body_enabled(defaults.RESPONSE_BODY_ENABLED)
        self.set_indexeddb_enabled(defaults.INDEXEDDB_ENABLED)
        self.set_webgl_enabled(defaults.WEBGL_ENABLED)
        self.set_html5_media_enabled(defaults.HTML5_MEDIA_ENABLED)
        self.set_media_source_enabled(defaults.MEDIA_SOURCE_ENABLED)

    def _setup_webpage_events(self):
        main_frame = self.web_page.mainFrame()
        self._load_finished = WrappedSignal(main_frame.loadFinished)
        main_frame.loadFinished.connect(self._on_load_finished)
        main_frame.urlChanged.connect(self._on_url_changed)
        main_frame.javaScriptWindowObjectCleared.connect(
            self._on_javascript_window_object_cleared)
        self._webpage_logger = WebkitEventLogger(self.logger)

    def set_custom_headers(self, headers):
        """
        Set custom HTTP headers to be sent with each request. Passed headers
        are merged with QWebKit default headers, overwriting QWebKit values
        in case of conflicts.
        """
        self.web_page.custom_headers = headers

    get_request_body_enabled = webpage_attribute_getter('request_body_enabled')
    set_request_body_enabled = webpage_attribute_setter('request_body_enabled')

    get_response_body_enabled = webpage_attribute_getter("response_body_enabled")
    set_response_body_enabled = webpage_attribute_setter("response_body_enabled")

    get_http2_enabled = webpage_attribute_getter("http2_enabled")
    set_http2_enabled = webpage_attribute_setter("http2_enabled")

    def set_resource_timeout(self, timeout):
        """ Set a default timeout for HTTP requests, in seconds. """
        self.web_page.resource_timeout = timeout

    def get_resource_timeout(self):
        """ Get a default timeout for HTTP requests, in seconds. """
        return self.web_page.resource_timeout

    def lock_navigation(self):
        self.web_page.navigation_locked = True

    def unlock_navigation(self):
        self.web_page.navigation_locked = False

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
            size = parse_size(size)
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
        self.logger.log("callback %s is connected to loadFinished" % callback_id,
                        min_level=3)
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
        return str(self.web_page.mainFrame().url().toString())

    def go(self, url, callback, errback, baseurl=None, http_method='GET',
           body=None, headers=None):
        """
        Go to an URL. This is similar to entering an URL in
        address tab and pressing Enter.
        """
        self.store_har_timing("_onStarted")

        if body is not None:
            body = to_bytes(body)

        headers_user_agent = get_header_value(headers, b"user-agent")
        if headers_user_agent:
            # User passed User-Agent header to go() so we need to set
            # consistent UA for all rendering requests.
            # Passing UA header to go() will have same effect as
            # splash:set_user_agent().
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
        super().close()
        self._closing_normally = True
        self._clear_event_handlers_storage()
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
            self.logger.log("Redirect or other non-fatal error detected",
                            min_level=2)
            return

        if self.web_page.is_ok(ok):  # or maybe_redirect:
            self.logger.log("loadFinished: ok", min_level=2)
        else:
            self._cancel_timers(self._timers_to_cancel_on_error)

            if self.web_page.error_loading(ok):
                self.logger.log("loadFinished: %s" % (str(self.web_page.error_info)),
                                min_level=1)
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
            self.logger.log("Error loading %s: %s" % (url, reply.errorString()),
                            min_level=1)

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

        self.logger.log("loadFinished: disconnecting callback %s" % callback_id,
                        min_level=3)
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

    def _cancel_all_timers(self):
        total_len = len(self._active_timers) + len(self._callback_proxies_to_cancel)
        self.logger.log("cancelling %d remaining timers" % total_len,
                        min_level=2)
        for timer in list(self._active_timers):
            self._cancel_timer(timer)
        for callback_proxy in self._callback_proxies_to_cancel:
            callback_proxy.use_up()

    def _on_url_changed(self, url):
        self.web_page.har.store_redirect(str(url.toString()))
        self._cancel_timers(self._timers_to_cancel_on_redirect)

    def _process_js_result(self, obj, allow_dom):
        if obj is None:
            return None

        if not isinstance(obj, dict):
            raise ValueError("Invalid input object: %r" % obj)

        allowed_types = {'Node', 'NodeList', 'other'} if allow_dom else {'other'}
        result_type = obj.get('type')

        if result_type not in allowed_types:
            raise ValueError("Invalid result type: %r" % result_type)

        if result_type == 'Node':
            # result is a single Node
            return self._html_element(obj['id'])
        elif result_type == 'NodeList':
            # Array of nodes
            return [self._html_element(node_id) for node_id in obj['ids']]
        elif result_type == "other":
            return obj.get('data', None)

    def _html_element(self, node_id):
        return HTMLElement(tab=self,
                           storage=self._elements_storage,
                           event_handlers_storage=self._event_handlers_storage,
                           events_storage=self._events_storage,
                           node_id=node_id)

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
        self._js_storage_initiated = False

        for idx, script in enumerate(self._autoload_scripts):
            # XXX: handle_errors=False is used to execute autoload scripts
            # in a global context (not inside a closure).
            # One difference is how are `function foo(){}` statements handled:
            # if executed globally, `foo` becomes an attribute of window;
            # if executed in a closure, `foo` is a name local to this closure.
            try:
                self.runjs(script, handle_errors=False)
            except Exception as e:
                msg = "Error in autoload script #{}: {}".format(idx, e)
                self.logger.log(msg, min_level=1)
                self.logger.log(traceback.format_exc(), min_level=1)

    def http_get(self, url, callback, headers=None, follow_redirects=True):
        """
        Send a GET request; call a callback with the reply as an argument.
        """
        self.http_client.get(url,
            callback=callback,
            headers=headers,
            follow_redirects=follow_redirects
        )

    def http_post(self, url, callback, headers=None, follow_redirects=True,
                  body=None):
        if body is not None:
            body = to_bytes(body)

        self.http_client.post(url,
                              callback=callback,
                              headers=headers,
                              follow_redirects=follow_redirects,
                              body=body)

    def evaljs(self, js_source, handle_errors=True, result_protection=True,
               dom_elements=True):
        """
        Run JS code in page context and return the result.

        If JavaScript exception or an syntax error happens
        and `handle_errors` is True then Python JsError
        exception is raised.

        When `result_protection` is True (default) protection against
        badly written or malicious scripts is activated. Disable it
        when the script result is known to be good, i.e. it only
        contains objects/arrays/primitives without circular references.

        When `dom_elements` is True (default) top-level DOM elements will be
        saved in JS field of window object under `self._elements_storage.name`
        key. The result of evaluation will be object with `type` property and
        `id` property. In JS the original DOM element can accessed through
        ``window[self._elements_storage.name][id]``.
        """
        frame = self.web_page.mainFrame()
        eval_expr = u"eval({})".format(escape_js(js_source))

        if dom_elements:
            self._init_js_objects_storage()
            eval_expr = store_dom_elements(eval_expr,
                                           self._elements_storage.name)
        if result_protection:
            eval_expr = get_sanitized_result_js(eval_expr)

        if handle_errors:
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

            result = res.get("result", None)
        else:
            result = qt2py(frame.evaluateJavaScript(eval_expr))

        return self._process_js_result(result, allow_dom=dom_elements)

    def runjs(self, js_source, handle_errors=True):
        """ Run JS code in page context and discard the result. """

        # If JS code returns something, and we just discard
        # the result of frame.evaluateJavaScript, then Qt still needs to build
        # a result - it could be costly. So the original JS code
        # is adjusted to make sure it doesn't return anything.
        self.evaljs(
            js_source="%s\n;undefined" % js_source,
            handle_errors=handle_errors,
            result_protection=False,
            dom_elements=False,
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
        callback_proxy = OneShotCallbackProxy(self, callback, errback,
                                              self.logger, timeout)
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
            renderer = QtWebkitScreenshotRenderer(
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
            "url": str(frame.url().toString()),
            "requestedUrl": str(frame.requestedUrl().toString()),
            "geometry": (g.x(), g.y(), g.width(), g.height()),
            "title": str(frame.title())
        }
        if html:
            res["html"] = str(frame.toHtml())

        if children:
            res["childFrames"] = [
                self._frame_to_dict(f, True, html)
                for f in frame.childFrames()
            ]
            res["frameName"] = str(frame.frameName())

        return res

    def mouse_click(self, x, y, button="left"):
        """Clicks elements on webpage.

        :param x integer with X screen position to click
        :param y integer with Y screen position to click
        :param button string specifying button type
        :return: None
        """
        # XXX only left click supported for now, we can add support and
        # tests for right click in the future if there is need for that.
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

    def select(self, selector):
        """ Select DOM element and return an instance of `HTMLElement`

        :param selector valid CSS selector
        :return element
        """
        js_query = u"document.querySelector({})".format(escape_js(selector))
        result = self.evaljs(js_query)

        if result == "":
            return None

        return result

    def select_all(self, selector):
        """ Select DOM elements and return a list of instances of `HTMLElement`

        :param selector valid CSS selector
        :return list of elements
        """
        js_query = u"document.querySelectorAll({})".format(escape_js(selector))
        return self.evaljs(js_query)

    def get_scroll_position(self):
        point = self.web_page.mainFrame().scrollPosition()
        return {'x': point.x(), 'y': point.y()}

    def set_scroll_position(self, x, y):
        point = QPoint(x, y)
        self.web_page.mainFrame().setScrollPosition(point)


class _JavascriptConsole(QObject):
    def __init__(self, parent=None):
        self.messages = []
        super(_JavascriptConsole, self).__init__(parent)

    @pyqtSlot(str)
    def log(self, message):
        self.messages.append(str(message))

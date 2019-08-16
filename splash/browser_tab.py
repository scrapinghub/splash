# -*- coding: utf-8 -*-
import abc
import base64
import functools
import os
import weakref
import traceback

from PyQt5.QtCore import (
    QObject, QSize, Qt, QTimer, pyqtSlot, QEvent,
    QPointF, QPoint, pyqtSignal,
)
from PyQt5.QtNetwork import QNetworkRequest

from splash import defaults
from splash.har.qt import cookies2har
from splash.network_manager import SplashQNetworkAccessManager
from splash.qtutils import (
    OPERATION_QT_CONSTANTS,
    MediaSourceEnabled,
    MediaEnabled,
    WrappedSignal,
    qt2py,
    qurl2ascii,
    to_qurl,
    qt_send_key,
    qt_send_text,
)
from splash.render_options import validate_size_str
from splash.errors import JsError, ScriptError
from splash.utils import to_bytes, get_id
from splash.jsutils import (
    get_sanitized_result_js,
    SANITIZE_FUNC_JS,
    get_process_errors_js,
    escape_js,
    store_dom_elements,
)
from splash.html_element import HTMLElement
from splash.log import SplashLogger


def skip_if_closing(meth):
    @functools.wraps(meth)
    def wrapped(self, *args, **kwargs):
        if self.closing:
            self.logger.log("%s is not called because BrowserTab "
                            "is closing" % meth.__name__, min_level=2)
            return
        return meth(self, *args, **kwargs)

    return wrapped


def escape_and_evaljs(frame, js_func):
    eval_expr = u"eval({})".format(escape_js(js_func))
    return frame.evaluateJavaScript(get_process_errors_js(eval_expr))


def webpage_option_getter(attr):
    """ Helper function for defining getters for web_page options, e.g.
    ``get_images_enabled = webpage_option_getter(QWebSettings.AutoLoadImages)``
    To be used in BrowserTab subclasses.
    """
    def _getter(self):
        settings = self.web_page.settings()
        return settings.testAttribute(attr)
    return _getter


def webpage_option_setter(attr, type_=None):
    """ Helper function for defining setters for web_page options, e.g.
    ``set_images_enabled = webpage_option_setter(QWebSettings.AutoLoadImages)``
    To be used in BrowserTab subclasses.
    """
    def _setter(self, value):
        if type_ is not None:
            value = type_(value)
        settings = self.web_page.settings()
        settings.setAttribute(attr, value)
    return _setter


def webpage_attribute_getter(attr):
    """ Helper function for defining getters for web_page attributes, e.g.
    ``get_foo_enabled = webpage_attribute_getter("foo")`` returns
    a value of ``webpage.foo`` attribute.
    """
    def _getter(self):
        return getattr(self.web_page, attr)
    return _getter


def webpage_attribute_setter(attr):
    """ Helper function for defining setters for web_page attributes, e.g.
    ``set_foo_enabled = webpage_attribute_setter("foo")`` sets
    a value of ``webpage.foo`` attribute.
    """
    def _setter(self, value):
        setattr(self.web_page, attr, value)
    return _setter


class BrowserTab(QObject):
    def __init__(self, render_options, verbosity, **kwargs):
        QObject.__init__(self)
        self.verbosity = verbosity
        self.closing = False
        self._uid = render_options.get_uid()
        self._timers_to_cancel_on_redirect = weakref.WeakKeyDictionary()  # timer: callback
        self._timers_to_cancel_on_error = weakref.WeakKeyDictionary()  # timer: callback
        self._active_timers = set()
        self.logger = SplashLogger(self._uid, self.verbosity)
        self.web_page = None  # implement it in a subclass

    @skip_if_closing
    def close(self):
        """ Destroy this tab """
        self.logger.log("close is requested by a script", min_level=2)
        self.closing = True

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

        self.logger.log("waiting %sms; timer %s" % (time_ms, id(timer)),
                        min_level=2)

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


class WebpageEventLogger(metaclass=abc.ABCMeta):
    """ Base class for objects which setup logging of webpage events """
    def __init__(self, logger: SplashLogger) -> None:
        self.logger = logger

    @abc.abstractmethod
    def add_web_page(self, web_page) -> None:
        pass


class ElementsStorage(QObject):
    """
    Object that allows to store JavaScript Node objects.

    This creates a JavaScript-compatible object (can be added to `window`)
    that has `get_id()` function which can be called from JavaScript for
    retrieving a unique id for each Node object
    """
    def __init__(self, parent):
        self.name = get_id()
        super(ElementsStorage, self).__init__(parent)

    @pyqtSlot(name="getId", result=str)
    def get_id(self):
        return get_id()


class Event(object):
    """
    Proxy object that allows to access JavaScript Event objects properties
    and methods.

    Properties are defined using `__getitem__` method and can be accessed using
    `self[key]` operation.

    To create the objects of this type you should pass an instance
    of `EventsStorage` and an id of the event by which it can be accessed
    in the events storage
    """
    def __init__(self, storage, id, event):
        self.storage = storage
        self.id = id
        self.event = event

    def __getitem__(self, item):
        return self.storage.get_event_property(self.id, item)

    def preventDefault(self):
        return self.storage.preventDefault.emit(self.id)

    def stopImmediatePropagation(self):
        return self.storage.stopImmediatePropagation.emit(self.id)

    def stopPropagation(self):
        return self.storage.stopPropagation.emit(self.id)

    def remove(self):
        return self.storage.remove_event(self.id)


class EventHandlersStorage(QObject):
    """
    Object that allows to store JavaScript event listeners.

    This creates a JavaScript-compatible object (can be added to `window`)
    that has `run_function()` function which is called from JS when the event
    is triggered and the event listener is called.
    """
    def __init__(self, parent, events_storage):
        self.name = get_id()
        self.events_storage = events_storage
        self.storage = {}
        super(EventHandlersStorage, self).__init__(parent)

    def add(self, func):
        func_id = get_id()

        event_wrapper = u"window[{storage_name}].add(event)".format(
            storage_name=escape_js(self.events_storage.name),
        )
        js_func = u"window[{storage_name}][{func_id}] = " \
                  u"function(event) {{ window[{storage_name}].run({func_id}, {event}, event) }}"\
            .format(
                storage_name=escape_js(self.name),
                func_id=escape_js(func_id),
                event=event_wrapper
            )

        escape_and_evaljs(self.parent().web_page.mainFrame(), js_func)

        self.storage[func_id] = func
        return func_id

    def remove(self, func_id):
        if self.storage.get(func_id, None) is not None:
            del self.storage[func_id]

    def clear(self):
        self.storage.clear()

    @pyqtSlot(str, str, 'QVariantMap', name="run")
    def run_function(self, func_id, event_id, event):
        if func_id not in self.storage:
            return
        wrapped_event = Event(self.events_storage, event_id, event)
        self.storage[func_id].on_call_after.append(wrapped_event.remove)
        self.storage[func_id](wrapped_event)


class EventsStorage(QObject):
    """
    Object that allows to store JavaScript Event objects and access them.

    This creates a JavaScript-compatible object (can be added to `window`)
    that has `get_id()` function which can be called from JavaScript for
    retrieving a unique id for each event object.

    After adding to the JS window object the `init_storage(self)` method
    should be called to initialize the storage. During the initialization
    the storage object is connected to the QT signals which allows to call
    appropriate methods of the specified event.
    """
    preventDefault = pyqtSignal(str)
    stopImmediatePropagation = pyqtSignal(str)
    stopPropagation = pyqtSignal(str)

    def __init__(self, parent):
        self.name = get_id()
        super(EventsStorage, self).__init__(parent)

    def init_storage(self):
        frame = self.parent().web_page.mainFrame()
        eval_expr = u"eval({})".format(escape_js("""
        (function() {{
            var storage = window[{storage_name}];

            storage.events = {{}};

            storage.callMethod = function(methodName) {{
                return function(eventId) {{
                    var eventsStorage = window[{storage_name}].events;
                    eventsStorage[eventId][methodName].call(eventsStorage[eventId]);
                }};
            }}

            storage.preventDefault.connect(storage.callMethod('preventDefault'))
            storage.stopImmediatePropagation.connect(storage.callMethod('stopImmediatePropagation'))
            storage.stopPropagation.connect(storage.callMethod('stopPropagation'))

            storage.add = function(event) {{
                var id = storage.getId()
                storage.events[id] = event;
                return id;
            }}
        }})()
        """.format(storage_name=escape_js(self.name))))

        frame.evaluateJavaScript(eval_expr)

    @pyqtSlot(name="getId", result=str)
    def get_id(self):
        return get_id()

    def get_event_property(self, event_id, property_name):
        js_func = """
        window[{storage_name}].events[{event_id}][{property_name}]
        """.format(
            storage_name=escape_js(self.name),
            event_id=escape_js(event_id),
            property_name=escape_js(property_name)
        )

        result = escape_and_evaljs(self.parent().web_page.mainFrame(), js_func)

        return result.get('result', None)

    def remove_event(self, event_id):
        js_func = """
        delete window[{storage_name}].events[{event_id}]
        """.format(
            storage_name=escape_js(self.name),
            event_id=escape_js(event_id),
        )
        escape_and_evaljs(self.parent().web_page.mainFrame(), js_func)


class OneShotCallbackProxy(QObject):
    """
    A proxy object that allows JavaScript to run Python callbacks.

    This creates a JavaScript-compatible object (can be added to `window`)
    that has functions `resume()` and `error()` that can be connected to
    Python callbacks.

    It is "one shot" because either `resume()` or `error()` should be called
    exactly _once_. It logs an error if the combined number of calls
    to these methods is greater than 1 (exception is not raised because
    calls may happen from JS, and Qt ends a process in such cases).

    If timeout is zero, then the timeout is disabled.
    """

    def __init__(self, parent, callback, errback, logger: SplashLogger,
                 timeout=0):
        self.name = get_id()
        self._used_up = False
        self._callback = callback
        self._errback = errback
        self.logger = logger

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
            self.logger.log("warning: resume() called on a one shot callback "
                             "that was already used up.", min_level=1)
            return

        self.use_up()
        self._callback(qt2py(value))

    @pyqtSlot(str, bool)
    def error(self, message, raise_=False):
        if self._used_up:
            self.logger.log("warning: error() called on a one shot callback "
                             "that was already used up.", min_level=1)
            return

        self.use_up()
        self._errback(message, raise_)

    def cancel(self, reason):
        if self._used_up:
            return
        self.use_up()
        self._errback("One shot callback canceled due to: %s." % reason,
                      raise_=False)

    def _timed_out(self):
        if self._used_up:
            return
        self.use_up()
        self._errback("One shot callback timed out while waiting for"
                      " resume() or error().", raise_=False)

    def use_up(self):
        self._used_up = True

        if self._timer is not None and self._timer.isActive():
            self._timer.stop()

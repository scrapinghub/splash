from __future__ import absolute_import
from functools import wraps

from splash.exceptions import DOMError
from splash.jsutils import escape_js
from splash.casperjs_utils import (
    VISIBLE_JS_FUNC,
    ELEMENT_INFO_JS,
    FIELD_VALUE_JS,
    FORM_VALUES_JS,
    SET_FIELD_VALUE_JS
)


DIMENSIONS_JS_FUNC = """
(function(elem) {
    var rect = elem.getClientRects()[0];
    return {"x":rect.left, "y": rect.top, "width": rect.width, "height": rect.height}
})(%s)
"""

FETCH_TEXT_JS_FUNC = """
(function(elem) {
    return (elem.textContent || elem.innerText || elem.value || '').trim();
})(%s)
"""

FILL_FORM_VALUES_JS = """
function (form, values, setFieldValue) {
  Object.keys(values).forEach(function (name) {
    var selector = "[name='" + name + "']";
    setFieldValue(selector, values[name], form);
  });
}
"""


def empty_strings_as_none(meth):
    @wraps(meth)
    def change_return_value_to_none_for_empty_string(*args, **kwargs):
        retval = meth(*args, **kwargs)
        return None if retval == '' else retval

    return change_return_value_to_none_for_empty_string


def escape_js_args(*args):
    return ','.join([
        arg.element_js if isinstance(arg, HTMLElement) else escape_js(arg)
        for arg in args
    ])


class HTMLElement(object):
    """ Class for manipulating DOM HTML Element """

    def __init__(self, tab, storage, event_handlers_storage, events_storage,
                 node_id):
        self.tab = tab
        self.storage = storage
        self.event_handlers_storage = event_handlers_storage
        self.events_storage = events_storage
        self.id = node_id
        self.element_js = self.get_element_js()
        msg = "HTMLElement is created with id=%s in object %s" % (
            self.id, self.element_js
        )
        self.tab.logger.log(msg, min_level=4)

    def get_element_js(self):
        """ Return JS object to which the element is assigned. """
        return 'window["%s"]["%s"]' % (self.storage.name, self.id)

    def assert_element_exists(self):
        """ Raise exception if the element no longer exists in DOM. """
        if not self.exists():
            raise DOMError({
                'type': DOMError.NOT_IN_DOM_ERROR,
                'message': "Element no longer exists in DOM"
            })

    def assert_node_type(self, node_type):
        """
        Raise an exception if the type of the element doesn't match node_type.
        """
        actual_type = self.node_property('nodeName').lower()
        if actual_type != node_type.lower():
            raise DOMError({
                'type': DOMError.NOT_COMPATIBLE_NODE_ERROR,
                'message': "Node should be {!r}, but got {!r}".format(
                    node_type, actual_type)
            })

    def exists(self):
        """ Return flag indicating whether element is in DOM """
        exists = self.tab.evaljs("document.contains(%s)" % self.element_js)
        return bool(exists)

    @empty_strings_as_none
    def node_property(self, property_name):
        """ Return value of the specified property of the element """
        return self.tab.evaljs(u"{element}[{property}]".format(
            element=self.element_js,
            property=escape_js(property_name)
        ))

    @empty_strings_as_none
    def set_node_property(self, property_name, property_value):
        """ Set value of the specified property of the element """
        return self.tab.evaljs(u"{element}[{property}] = {value}".format(
            element=self.element_js,
            property=escape_js(property_name),
            value=escape_js(property_value)
        ))

    def get_node_style(self, property_name):
        """ Get value of the style property of the element """
        return self.tab.evaljs(u"{element}.style[{property}]".format(
            element=self.element_js,
            property=escape_js(property_name),
        ))

    def set_node_style(self, property_name, property_value):
        """ Set value of the style property of the element """
        return self.tab.evaljs(u"{element}.style[{property}] = {value}".format(
            element=self.element_js,
            property=escape_js(property_name),
            value=escape_js(property_value)
        ))

    def node_method(self, method_name):
        """ Return function which calls the specified method of the element """

        @empty_strings_as_none
        def call(*args):
            return self.tab.evaljs(u"{element}[{method}]({args})".format(
                element=self.element_js,
                method=escape_js(method_name),
                args=escape_js_args(*args)
            ))

        return call

    def mouse_click(self, x=0, y=0, button="left"):
        """ Click on the element """
        self.assert_element_exists()
        dimensions = self._get_dimensions()
        self.tab.mouse_click(dimensions["x"] + x, dimensions["y"] + y, button)

    def mouse_hover(self, x=0, y=0):
        """ Hover over the element """
        self.assert_element_exists()
        dimensions = self._get_dimensions()
        self.tab.mouse_hover(dimensions["x"] + x, dimensions["y"] + y)

    def _get_dimensions(self):
        return self.tab.evaljs(DIMENSIONS_JS_FUNC % self.element_js)

    def styles(self):
        """ Return computed styles of the element """
        return self.tab.evaljs("getComputedStyle(%s)" % self.element_js)

    def bounds(self):
        """ Return bounding client rectangle of the element"""
        return self.tab.evaljs("%s.getBoundingClientRect()" % self.element_js)

    def png(self, width=None, scale_method=None, pad=None):
        """ Return screenshot of the element in PNG format.

        Optional `pad` can be provided which can be in two formats:
          - integer containing amount of pad for all sides
            (top, left, bottom, right)
          - tuple with `left`, `top`, `right`, `bottom` integer
            values for padding

        Padding value can be negative which means that the image will be cropped.
        """
        if not self.exists() or not self.visible():
            return None

        region = _bounds_to_region(self.bounds(), pad)
        return self.tab.png(width, region=region, scale_method=scale_method)

    def jpeg(self, width=None, scale_method=None, quality=None, pad=None):
        """ Return screenshot of the element in JPEG format.

        Optional `pad` can be provided which can be in two formats:
          - integer containing amount of pad for all sides
            (top, left, bottom, right)
          - tuple with `left`, `top`, `right`, `bottom` integer
            values for padding

        Padding value can be negative which means that the image will be cropped.
        """
        if not self.exists() or not self.visible():
            return None
        region = _bounds_to_region(self.bounds(), pad)
        return self.tab.jpeg(width, region=region, scale_method=scale_method,
                             quality=quality)

    def visible(self):
        """ Return flag indicating whether element is visible """
        self.assert_element_exists()
        return self.tab.evaljs(u"({visible_func})({element})".format(
            visible_func=VISIBLE_JS_FUNC,
            element=self.element_js
        ))

    def text(self):
        """ Return text of the element """
        return self.tab.evaljs(FETCH_TEXT_JS_FUNC % self.element_js)

    def info(self):
        """ Return information about the element """
        return self.tab.evaljs(u"({element_info_func})({element}, {visible_func})".format(
            element_info_func=ELEMENT_INFO_JS,
            element=self.element_js,
            visible_func=VISIBLE_JS_FUNC
        ))

    def field_value(self):
        """ Return the value of the element if it is a field """
        return self.tab.evaljs(u"({field_value_func})({element})".format(
            field_value_func=FIELD_VALUE_JS,
            element=self.element_js
        ))

    def form_values(self, values='auto'):
        """ Return all values of the element if it is a form"""
        self.assert_node_type('form')

        return self.tab.evaljs(u"({form_values_func})({element}, {values}, {field_value_func})".format(
            form_values_func=FORM_VALUES_JS,
            field_value_func=FIELD_VALUE_JS,
            values=escape_js(values),
            element=self.element_js
        ))

    def fill(self, values):
        """ Fill the values of the element """
        return self.tab.evaljs(u"({fill_form_values_func})({element}, {values}, {set_field_value})".format(
            fill_form_values_func=FILL_FORM_VALUES_JS,
            element=self.element_js,
            values=escape_js(values),
            set_field_value=SET_FIELD_VALUE_JS
        ))

    def send_keys(self, text):
        """ Send key events to the element separated by whitespaces """
        if not self.focused():
            self.mouse_click()
        self.tab.send_keys(text)

    def send_text(self, text):
        """ Send text to the element """
        if not self.focused():
            self.mouse_click()
        self.tab.send_text(text)

    def focused(self):
        """ Return True if the current element is focused """
        return self.tab.evaljs(
            "{} === document.activeElement".format(self.element_js)
        )

    def set_event_handler(self, event_name, handler):
        """ Set on-event type event listeners to the element """
        handler_id = self.event_handlers_storage.add(handler)

        func = u"window[{storage_name}][{func_id}]".format(
            storage_name=escape_js(self.event_handlers_storage.name),
            func_id=escape_js(handler_id),
        )

        self.tab.evaljs(u"{element}['on' + {event_name}] = {func}".format(
            element=self.element_js,
            event_name=escape_js(event_name),
            func=func
        ))

        return handler_id

    def unset_event_handler(self, event_name, handler_id):
        """ Remove on-event type event listeners from the element """
        self.tab.evaljs(u"{element}['on' + {event_name}] = null".format(
            element=self.element_js,
            event_name=escape_js(event_name),
        ))
        self.event_handlers_storage.remove(handler_id)

    def add_event_handler(self, event_name, handler, options=None):
        """ Add event listeners to the element for the specified event """
        handler_id = self.event_handlers_storage.add(handler)

        func = u"window[{storage_name}][{func_id}]".format(
            storage_name=escape_js(self.event_handlers_storage.name),
            func_id=escape_js(handler_id),
        )

        self.tab.evaljs(u"{element}.addEventListener({event_name}, {func}, {options})".format(
            element=self.element_js,
            event_name=escape_js(event_name),
            func=func,
            options=escape_js(options)
        ))

        return handler_id

    def remove_event_handler(self, event_name, handler_id):
        """
        Remove event listeners from the element for the specified event
        and handler.
        """
        func = u"window[{storage_name}][{func_id}]".format(
            storage_name=escape_js(self.event_handlers_storage.name),
            func_id=escape_js(handler_id),
        )
        self.tab.evaljs(u"{element}.removeEventListener({event_name}, {func})".format(
            element=self.element_js,
            event_name=escape_js(event_name),
            func=func
        ))
        self.event_handlers_storage.remove(handler_id)

    def submit(self):
        """ Submit form element """
        self.assert_node_type('form')
        self.node_method('submit')()


def _padded(region, pad):
    """
    >>> _padded([1, 1, 4, 4], [0, 1, 2 ,3])
    (1, 0, 6, 7)
    >>> _padded([1, 1, 4, 4], 2)
    (-1, -1, 6, 6)
    """
    if not pad:
        return region
    if isinstance(pad, (int, float)):
        pad = (pad, pad, pad, pad)
    return (
        region[0] - pad[0],
        region[1] - pad[1],
        region[2] + pad[2],
        region[3] + pad[3]
    )


def _bounds_to_region(bounds, pad):
    region = bounds["left"], bounds["top"], bounds["right"], bounds["bottom"]
    return _padded(region, pad)

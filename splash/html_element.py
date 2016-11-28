from splash.exceptions import DOMError, JsError
from splash.jsutils import escape_js
from splash.casperjs_utils import (
    VISIBLE_JS_FUNC,
    ELEMENT_INFO_JS,
    FIELD_VALUE_JS,
    FORM_VALUES_JS
)

DIMENSIONS_JS_FUNC = """
(function(elem) {
    var rect = elem.getClientRects()[0];
    return {"x":rect.left, "y": rect.top}
})(%s)
"""

FETCH_TEXT_JS_FUNC = """
(function(elem) {
    return elem.textContent || elem.innerText || elem.value || '';
})(%s)
"""


class HTMLElement(object):
    """ Class for manipulating DOM HTML Element """

    def __init__(self, tab, storage, node):
        if not node:
            raise DOMError({
                'message': "Cannot find the requested element"
            })

        self.tab = tab
        self.storage = storage
        self.id = node["id"]
        self.element_js = self.get_element_js()
        self.tab.logger.log("HTMLElement is created with id = %s in object %s" % (self.id, self.element_js),
                            min_level=4)

    def get_element_js(self):
        """ Return JS object to which the element is assigned """
        return "window['%s']['%s']" % (self.storage.name, self.id)

    def assert_element_exists(self):
        """ Raise exception if the element no longer exists in DOM """
        if not self.exists():
            raise DOMError({
                'message': "Element no longer exists in DOM"
            })

    def assert_node_type(self, node_type):
        actual_type = self.node_property('nodeName').lower()
        """ Raise exception if the type of the element doesn't match with the provided one """
        if actual_type != node_type.lower():
            raise DOMError({
                'message': "Node should be {!r}, but got {!r}".format(node_type, actual_type)
            })

    def return_html_element_if_node(self, result):
        """ Returns a new instance of HTMLElement if the `result.type` is "node" """
        if isinstance(result, dict) and result.get("type", None) == 'node':
            return HTMLElement(self.tab, self.storage, result)

        return result

    def assert_editable(self):
        """ Raise exception if the element doesn't accept user input """
        info = self.info()
        tag = info["nodeName"].lower()
        type = info["attributes"].get("type")
        supported = ["color", "date", "datetime", "datetime-local", "email",
                     "hidden", "month", "number", "password", "range", "search",
                     "tel", "text", "time", "url", "week"]
        is_textarea = tag == "textarea"
        is_valid_input = tag == "input" and type in supported
        is_contenteditable = info["attributes"].get("contenteditable") is not None

        if not (is_textarea or is_valid_input or is_contenteditable):
            raise DOMError({
                'message': "Node should be editable"
            })

    def exists(self):
        """ Return flag indicating whether element is in DOM """
        try:
            exists = self.tab.evaljs("document.contains(%s)" % self.element_js)
            return bool(exists)
        except JsError:
            return False

    def node_property(self, property_name):
        """ Return value of the specified property of the element """
        self.assert_element_exists()
        result = self.tab.evaljs(u"{element}[{property}]".format(
            element=self.element_js,
            property=escape_js(property_name)
        ))
        return self.return_html_element_if_node(result)

    def node_method(self, method_name):
        """ Return function which will call the specified method of the element """
        self.assert_element_exists()

        def call(*args):
            result = self.tab.evaljs(u"{element}[{method}]({args})".format(
                element=self.element_js,
                method=escape_js(method_name),
                args=escape_js(*args)
            ))
            return self.return_html_element_if_node(result)

        return call

    def mouse_click(self, button="left"):
        """ Click on the element """
        self.assert_element_exists()
        dimensions = self.tab.evaljs(
            DIMENSIONS_JS_FUNC % self.element_js,
        )

        self.tab.mouse_click(dimensions["x"], dimensions["y"], button)

    def mouse_hover(self):
        """ Hover over the element """
        self.assert_element_exists()
        dimensions = self.tab.evaljs(
            DIMENSIONS_JS_FUNC % self.element_js,
        )

        self.tab.mouse_hover(dimensions["x"], dimensions["y"])

    def get_styles(self):
        """ Return computed styles of the element """
        self.assert_element_exists()
        return self.tab.evaljs("getComputedStyle(%s)" % self.element_js, result_protection=False)

    def get_bounds(self):
        """ Return bounding client rectangle of the element"""
        self.assert_element_exists()
        return self.tab.evaljs("%s.getBoundingClientRect()" % self.element_js, result_protection=False)

    def png(self, width=None, height=None, scale_method=None):
        """ Return screenshot of the element in PNG format """
        self.assert_element_exists()

        if not self.visible():
            return None

        bounds = self.get_bounds()
        region = (bounds["left"], bounds["top"], bounds["right"], bounds["bottom"])
        return self.tab.png(width, height, region=region, scale_method=scale_method)

    def jpeg(self, width=None, height=None, scale_method=None, quality=None):
        """ Return screenshot of the element in JPEG format """
        self.assert_element_exists()

        if not self.visible():
            return None

        bounds = self.get_bounds()
        region = (bounds["left"], bounds["top"], bounds["right"], bounds["bottom"])
        return self.tab.jpeg(width, height, region=region, scale_method=scale_method, quality=quality)

    def visible(self):
        """ Return flag indicating whether element is visible """
        self.assert_element_exists()
        return self.tab.evaljs(u"({visible_func})({element})".format(
            visible_func=VISIBLE_JS_FUNC,
            element=self.element_js
        ))

    def fetch_text(self):
        """ Return text of the element """
        self.assert_element_exists()
        return self.tab.evaljs(FETCH_TEXT_JS_FUNC % self.element_js)

    def info(self):
        """ Return information about the element """
        self.assert_element_exists()

        return self.tab.evaljs(u"({element_info_func})({element}, {visible_func})".format(
            element_info_func=ELEMENT_INFO_JS,
            element=self.element_js,
            visible_func=VISIBLE_JS_FUNC
        ))

    def field_value(self):
        """ Return the value of the element if it is a field """
        self.assert_element_exists()

        return self.tab.evaljs(u"({field_value_func})({element})".format(
            field_value_func=FIELD_VALUE_JS,
            element=self.element_js
        ))

    def form_values(self):
        """ Return all values of the element if it is a form"""
        self.assert_element_exists()
        self.assert_node_type('form')

        return self.tab.evaljs(u"({form_values_func})({element}, {field_value_func})".format(
            form_values_func=FORM_VALUES_JS,
            field_value_func=FIELD_VALUE_JS,
            element=self.element_js
        ))

    def send_keys(self, text):
        """ Send key events to the element separated by whitespaces """
        self.assert_editable()

        self.mouse_click()
        self.tab.send_keys(text)

    def send_text(self, text):
        """ Send text to the element """
        self.assert_editable()

        self.mouse_click()
        self.tab.send_text(text)

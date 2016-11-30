# -*- coding: utf-8 -*-
import json


def escape_js(*args):
    return json.dumps(args, ensure_ascii=False)[1:-1]


# JS function which only allows plain arrays/objects and other primitives
# with a restriction on maximum allowed depth.
# A more natural way would be to use JSON.stringify,
# but user can override global JSON object to bypass protection.
SANITIZE_FUNC_JS = u"""
function (obj, max_depth){
    max_depth = max_depth ? max_depth : 100;
    function _s(o, d) {
        if (d <= 0) {
            throw Error("Object is too deep or recursive");
        }
        if (o === null) {
            return "";  // this is the way Qt handles it
        }
        if (typeof o == 'object') {
            if (Array.isArray(o)) {
                var res = [];
                for (var i = 0; i < o.length; i++) {
                    res[i] = _s(o[i], d-1);
                }
                return res;
            }
            else if (
                    (Object.getPrototypeOf(o) == Object.prototype) ||
                    (o instanceof CSSStyleDeclaration)) {
                var res = {};
                for (var key in o) {
                    if (o.hasOwnProperty(key)) {
                        res[key] = _s(o[key], d-1);
                    }
                }
                return res;
            }
            else if (o instanceof Date) {
                return o.toJSON();
            }
            else if (o instanceof ClientRect) {
                return {
                    top: o.top, left: o.left, bottom: o.bottom, right: o.right,
                    width: o.width, height: o.height,
                };
            }
            else if (o instanceof ClientRectList) {
                return _s(Array.prototype.slice.call(o))
            }
            else if (o instanceof NamedNodeMap) {
                var nodes = {};
                Array.prototype.forEach.call(o, function(node) {
                    nodes[node.name.toLowerCase()] = node.value;
                });
                return nodes;
            }
            else if (o instanceof DOMTokenList) {
                return _s(Array.prototype.slice.call(o))
            }
            else {
                // likely host object
                return undefined;
            }
        }
        else if (typeof o == 'function') {
            return undefined;
        }
        else {
            return o;  // native type
        }
    }
    return _s(obj, max_depth);
}
"""


def get_sanitized_result_js(expression, max_depth=0):
    """
    Return a string with JavaScript code which returns a sanitized result of
    the ``expression``: only allow objects/arrays/other primitives are allowed,
    and an exception is raised for objects/arrays which are too deep.

    ``expression`` should be a JS string constant (already in quotes) or
    any other JS expression.

    Use it to sanitize data which should be returned from
    QWebFrame.evaluateJavaScript - Qt5 can go mad if we try to return something
    else (objects with circular references, DOM elements, ...).
    """
    return u"({sanitize_func})({expression}, {max_depth})".format(
        sanitize_func=SANITIZE_FUNC_JS,
        expression=expression,
        max_depth=max_depth
    )


STORE_DOM_ELEMENTS_JS = u"""
function (elements_storage_name, o) {
    var storage = window[elements_storage_name];

    function storeNode(node) {
        var id = storage.getId();
        Object.defineProperty(storage, id, {
            configurable: false,
            enumerable: false,
            writable: false,
            value: node,
        });
        return id;
    }

    if (o instanceof Node) {
        var id = storeNode(o);
        return {
            type: 'Node',
            id: id,
        }
    }
    else if (o instanceof NodeList) {
        var ids = Array.prototype.slice.call(o).map(storeNode);
        return {
            type: 'NodeList',
            ids: ids,
        }
    }
    return {
        type: 'other',
        data: o,
    };
}
"""


def store_dom_elements(expression, elements_storage_name):
    return u"({store_func})('{elements_storage_name}', {expression})".format(
        store_func=STORE_DOM_ELEMENTS_JS,
        elements_storage_name=elements_storage_name,
        expression=expression
    )


def get_process_errors_js(expression):
    """
    Return JS code which evaluates an ``expression`` and
    returns ``{error: false, result: ...}`` if there is no exception
    or ``{error: true, errorType: ..., errorMessage: ..., errorRepr: ...}``
    if expression raised an error when evaluating.
    """
    return u"""
    (function () {
      try {
        return {
          error: false,
          result: %(expression)s,
        }
      }
      catch (e) {
        return {
          error: true,
          errorType: e.name,
          errorMessage: e.message,
          errorRepr: e.toString(),
        };
      }
    })()
    """ % dict(expression=expression)

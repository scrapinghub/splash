# Copyright (c) 2011-2015 Nicolas Perriault
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is furnished
# to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

VISIBLE_JS_FUNC = """
function(elem) {
    var style;
    try {
        style = window.getComputedStyle(elem, null);
    } catch (e) {
        return false;
    }
    var hidden = style.visibility === 'hidden' || style.display === 'none';
    if (hidden) {
        return false;
    }
    if (style.display === "inline" || style.display === "inline-block") {
        return true;
    }
    return elem.clientHeight > 0 && elem.clientWidth > 0;
}
"""

ELEMENT_INFO_JS = """
function(element, visible) {
    var bounds = element.getBoundingClientRect();
    var attributes = {};
    [].forEach.call(element.attributes, function(attr) {
        attributes[attr.name.toLowerCase()] = attr.value;
    });
    return {
        nodeName: element.nodeName.toLowerCase(),
        attributes: attributes,
        tag: element.outerHTML,
        html: element.innerHTML,
        text: element.textContent || element.innerText,
        x: bounds.left,
        y: bounds.top,
        width: bounds.width,
        height: bounds.height,
        visible: visible(element)
    };
}
"""

FIELD_VALUE_JS = """
function(field) {
    var nodeName, type;

    if (!(field instanceof HTMLElement)) {
        var error = new Error('getFieldValue: Invalid field ; only HTMLElement is supported');
        error.name = 'FieldNotFound';
        throw error;
    }

    nodeName = field.nodeName.toLowerCase();
    type = field.hasAttribute('type') ? field.getAttribute('type').toLowerCase() : 'text';
    if (nodeName === "select" && field.multiple) {
        return [].filter.call(field.options, function(option){
            return !!option.selected;
        }).map(function(option){
            return option.value || option.text;
        });
    }
    if (type === 'radio') {
        return field.checked ? field.value : null;
    }
    if (type === 'checkbox') {
        return field.checked;
    }
    return field.value || '';
}
"""

FORM_VALUES_JS = """
function(form, getField) {
    var values = {}, checked = {};

    [].forEach.call(form.elements, function(elm) {
        var name = elm.getAttribute('name');
        var value = getField(elm);
        var multi = !!value && elm.hasAttribute('type') &&
                    elm.type === 'checkbox' ? elm.value : value;
        if (!!name && value !== null && !(elm.type === 'checkbox' && value === false)) {
            if (typeof values[name] === "undefined") {
                values[name] = value;
                checked[name] = multi;
            } else {
                if (!Array.isArray(values[name])) {
                    values[name] = [checked[name]];
                }
                values[name].push(multi);
            }
        }
    });
    return values;
}
"""

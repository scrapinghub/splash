# Source: https://github.com/casperjs/casperjs/blob/master/modules/clientutils.js
#
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
function(field, multi) {
  var nodeName, type;

  if (!(field instanceof HTMLElement)) {
    throw new Error('getFieldValue: Invalid field ; only HTMLElement is supported');
  }

  nodeName = field.nodeName.toLowerCase();
  type = field.hasAttribute('type') ? field.getAttribute('type').toLowerCase() : 'text';

  if (nodeName === 'select' && field.multiple) {
    return [].filter.call(field.options, function (option) {
      return !!option.selected;
    }).map(function (option) {
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
function(form, returnValuesType, getField) {
  var values = {}, checked = {};

  [].forEach.call(form.elements, function (elm) {
    var name = elm.getAttribute('name');
    var value = getField(elm);

    var multi = !!value && elm.hasAttribute('type') && elm.type === 'checkbox' ? elm.value : value;

    if (!!name && value !== null && !(elm.type === 'checkbox' && value === false)) {
      switch (returnValuesType) {
        case 'list':
          values[name] = values[name] || [];
          if (Array.isArray(multi)) {
            values[name] = values[name].concat(multi);
          } else {
            values[name].push(multi);
          }
          break;
        case 'first':
          if (typeof values[name] === 'undefined') {
            values[name] = Array.isArray(multi) ? multi[0] : value;
          }
          break;
        case 'auto':
        case null:
        case undefined:
          if (typeof values[name] === 'undefined') {
            values[name] = value;
            checked[name] = multi;
          } else {
            if (!Array.isArray(values[name])) {
              values[name] = [checked[name]];
            }
            values[name].push(multi);
          }

      }
    }
  });
  return values;
}
"""

# a little bit modified version to support filling text inputs with several values
SET_FIELD_VALUE_JS = """
(function () {
  function setFieldValue(selector, value, scope) {
    var fields = (document || scope).querySelectorAll(selector);
    var values = value;

    if (!Array.isArray(value)) {
      values = [value];
    }

    if (fields && fields.length > 1) {
      fields = [].filter.call(fields, function (elm) {
        if (elm.nodeName.toLowerCase() === 'input' &&
          ['checkbox', 'radio'].indexOf(elm.getAttribute('type')) !== -1) {
          return values.indexOf(elm.getAttribute('value')) !== -1;
        }
        return true;
      });
      [].forEach.call(fields, function (elm, index) {
        setField(elm, value, index);
      });
    } else {
      setField(fields[0], value);
    }
    return true;
  }

  function setField(field, value, index) {
    var filter;
    value = value || "";

    if (!(field instanceof HTMLElement)) {
      throw new Error('Invalid field ; only HTMLElement is supported');
    }

    try {
      field.focus();
    } catch (e) {
    }

    filter = String(field.getAttribute('type') ? field.getAttribute('type') : field.nodeName).toLowerCase();
    switch (filter) {
      case "checkbox":
      case "radio":
        field.checked = value ? true : false;
        break;
      case "file":
        throw new Error("File field is not supported");
        break;
      case "select":
        if (field.multiple) {
          [].forEach.call(field.options, function (option) {
            option.selected = value.indexOf(option.value) !== -1;
          });
          // If the values can't be found, try search options text
          if (field.value === "") {
            [].forEach.call(field.options, function (option) {
              option.selected = value.indexOf(option.text) !== -1;
            });
          }
        } else {
          if (value === "") {
            field.selectedIndex = -1;
          } else {
            field.value = value;
          }

          // If the value can't be found, try search options text
          if (field.value !== value) {
            [].some.call(field.options, function (option) {
              option.selected = value === option.text;
              return value === option.text;
            });
          }
        }
        break;
      default:
        if (Array.isArray(value)) {
          field.value = value[index];
        } else {
          field.value = value;
        }
    }

    ['change', 'input'].forEach(function (name) {
      var event = document.createEvent("HTMLEvents");
      event.initEvent(name, true, true);
      field.dispatchEvent(event);
    });

    // blur the field
    try {
      field.blur();
    } catch (err) {
    }
  }

  return setFieldValue;
})()
"""
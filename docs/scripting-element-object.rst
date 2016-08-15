.. _splash-element:

Element Object
==============

Element objects are created by :ref:`splash-select` and :ref:`splash-select-all`.

.. _splash-element-attributes:

Attributes
~~~~~~~~~~

.. _splash-element-node:

element.node
------------

``element.node`` is a object that contains almost all DOM element attributes and methods.

The list of supported properties (in brackets is specified whether the property is read-only):

Properties inherited from HTMLElement_:
    - accessKey (No)
    - accessKeyLabel (Yes)
    - contentEditable (No)
    - isContentEditable (Yes)
    - dataset (Yes)
    - dir (No)
    - draggable (No)
    - hidden (No)
    - lang (No)
    - offsetHeight (Yes)
    - offsetLeft (Yes)
    - offsetParent (Yes)
    - offsetTop (Yes)
    - spellcheck (No)
    - style (No) - returns the table with styles which can be modified
    - tabIndex (No)
    - title (No)
    - translate (No)

Properties inherited from Element_:
    - attributes (Yes) - returns the table of attributes of the element
    - classList (Yes) - returns the table of class names of the element
    - className (No)
    - clientHeight (Yes)
    - clientLeft (Yes)
    - clientTop (Yes)
    - clientWidth (Yes)
    - id (No)
    - innerHTML (No)
    - localeName (Yes)
    - namespaceURI (Yes)
    - nextElementSibling (Yes)
    - outerHTML (No)
    - prefix (Yes)
    - previousElementSibling (Yes)
    - scrollHeight (Yes)
    - scrollLeft (No)
    - scrollTop (No)
    - scrollWidth (Yes)
    - tabStop (No)
    - tagName (Yes)

Properties inherited from Node_:
    - baseURI (Yes)
    - childNodes (Yes)
    - firstChild (Yes)
    - lastChild (Yes)
    - nextSibling (Yes)
    - nodeName (Yes)
    - nodeType (Yes)
    - nodeValue (No)
    - ownerDocument (Yes)
    - parentNode (Yes)
    - parentElement (Yes)
    - previousSibling (Yes)
    - rootNode (Yes)
    - textContent (No)

The list of supported methods:

Methods inherited from HTMLElement_:
    - blur
    - click
    - focus

Methods inherited from Element_:
    - getAttribute
    - getAttributeNS
    - getBoundingClientRect
    - getClientRects
    - getElementsByClassName
    - getElementsByTagName
    - getElementsByTagNameNS
    - hasAttribute
    - hasAttributeNS
    - hasAttributes
    - querySelector
    - querySelectorAll
    - releasePointerCapture
    - remove
    - removeAttribute
    - removeAttributeNS
    - requestFullscreen
    - requestPointerLock
    - scrollIntoView
    - setAttribute
    - setAttributeNS
    - setPointerCapture

Methods inherited from Node_:
    - appendChild
    - cloneNode
    - compareDocumentPosition
    - contains
    - hasChildNodes
    - insertBefore
    - isDefaultNamespace
    - isEqualNode
    - isSameNode
    - lookupPrefix
    - lookupNamespaceURI
    - normalize
    - removeChild
    - replaceChild

Also, you can attach event handlers to the specified event. When the handler is called it will
receive ``event`` table with the almost all available methods and properties.

.. code-block:: lua

    function main(splash)
        local element = splash:select('.element')

        local x, y = 0, 0

        element.onclick = function(event)
            event:preventDefault()
            x = event.clientX
            y = event.clientY
        end

        assert(splash:wait(10))

        return x, y
    end


The following fields are read-only.

.. _HTMLElement: https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement
.. _Element: https://developer.mozilla.org/en-US/docs/Web/API/Element
.. _Node: https://developer.mozilla.org/en-US/docs/Web/API/Node
.. _Event: https://developer.mozilla.org/en-US/docs/Web/API/Event


.. _splash-element-inner_id:

element.inner_id
----------------

Id of the inner representation of the element.

Methods
~~~~~~~

To modify or retrieve some information about the element you can use the following methods.
Note that all of the following methods return flag indicating whether the operation was
successful or not. The methods returns ``ok, reason_or_value`` pair. If ``ok`` is nil
then error happened during the operation; ``reason`` provides an information about error type;
otherwise ``ok`` is ``true`` and the returned value is stored in the second variable.


.. _splash-element-exists:

element:exists
--------------

Check whether the element exists in DOM. If the element doesn't exist some of the methods will fail raising
the error flag.

**Signature:** ``exists = element:exists()``

**Returns:** ``exists`` indicated whether the element exists.

**Async:** no.


.. _splash-element-mouse-click:


element:mouse_click
-------------------

Trigger mouse click event on the element.

**Signature:** ``ok, reason = element:mouse_click(x, y)``

**Parameters:**

* x - optional, x coordinate relative to the left corner of the element
* y - optional, y coordinate relative to the top corner of the element

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during the
function call; ``reason`` provides an information about error type.

**Async:** no.

If x or y coordinate is not provided they will be set to 0 and the click will be triggered
on the left-top corner of the element. The coordinates can have a negative value which means
the click will be triggered outside of the element.

Mouse events are not propagated immediately, to see consequences of click
reflected in page source you must call :ref:`splash-wait`

See more about mouse events in :ref:`splash-mouse-click`.


.. _splash-element-mouse-hover:

element:mouse_hover
-------------------

Trigger mouse hover (JavaScript mouseover) event on the element.

**Signature:** ``ok, reason = element:mouse_hover(x, y)``

**Parameters:**

* x - optional, x coordinate relative to the left corner of the element
* y - optional, y coordinate relative to the top corner of the element

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during the
function call; ``reason`` provides an information about error type.

**Async:** no.

If x or y coordinate is not provided they will be set to 0 and the click will be triggered
on the left-top corner of the element. The coordinates can have a negative value which means
the click will be triggered outside of the element.

Mouse events are not propagated immediately, to see consequences of click
reflected in page source you must call :ref:`splash-wait`

See more about mouse events in :ref:`splash-mouse-click`.


.. _splash-element-get-styles:

element:get_styles
------------------

Return the computed styles of the element.

**Signature:** ``styles = element:get_styles()``

**Returns:** ``styles`` is a table with computed styles of the element.

**Async:** no.

Example of getting the font size of the element using this method.

.. code-block:: lua

    function main(splash)
        local element = splash:select('.element')
        return element:get_styles()['font-size']
    end


.. _splash-element-get-bounds:

element:get_bounds
------------------

Return the bounding client rectangle of the element

**Signature:** ``bounds = element:get_bounds()``

**Returns:** ``bounds`` is a table with the client bounding rectangle with the ``top``, ``right``,
``bottom`` and ``left`` coordinates.

**Async:** no.

Example of getting the bounds of the element.

.. code-block:: lua

    function main(splash)
        local element = splash:select('.element')
        return element:get_bounds()
        -- e.g. bounds is { top = 10, right = 20, bottom = 20, left = 10 }
    end


.. _splash-element-png:

element:png
-----------

Return a screenshot of the element in PNG format

**Signature:** ``ok, shot = element:png{width=nil, height=nil, scale_method='raster', pad=0}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``;
* pad - optional, integer or ``{left, top, right, bottom}`` values of padding

**Returns:** ``ok, shot`` pair. If ``ok`` is nil then error happened during the
function call; ``shot`` provides an information about error type; otherwise
``shot`` is a PNG screenshot data, as a :ref:`binary object <binary-objects>`.
When the result is empty (e.g. if the element is not visible) ``nil`` is returned.

**Async:** no.

*pad* parameter sets the padding of the resulting image. If it is a single integer then the
padding from all sides will be equal. If the value of the padding is positive the resulting screenshot
will be expanded by the specified amount of pixes. And if the value of padding is negative the resulting
screenshot will be shrunk by the specified amount of pixes.

See more in :ref:`splash-png`.


.. _splash-element-jpeg:

element:jpeg
------------

Return a screenshot of the element in JPEG format

**Signature:** ``ok, shot = element:jpeg{width=nil, height=nil, scale_method='raster', quality=75, region=nil, pad=0}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``;
* quality - optional, quality of JPEG image, integer in range from ``0`` to ``100``;
* pad - optional, integer or ``{left, top, right, bottom}`` values of padding

**Returns:** ``ok, shot`` pair. If ``ok`` is nil then error happened during the
function call; ``shot`` provides an information about error type; otherwise
``shot`` is a JPEG screenshot data, as a :ref:`binary object <binary-objects>`.
When the result is empty (e.g. if the element is not visible) ``nil`` is returned.

**Async:** no.

*pad* parameter sets the padding of the resulting image. If it is a single integer then the
padding from all sides will be equal. If the value of the padding is positive the resulting screenshot
will be expanded by the specified amount of pixes. And if the value of padding is negative the resulting
screenshot will be shrunk by the specified amount of pixes.

See more in :ref:`splash-jpeg`.


.. _splash-element-visible:

element:visible
---------------

Check whether the element is visible.

**Signature:** ``visible = element:visible()``

**Returns:** ``visible`` indicated whether
the element is visible.

**Async:** no.


.. _splash-element-fetch-text:

element:fetch_text
------------------

Fetch a text information from the element

**Signature:** ``text = element:fetch_text()``

**Returns:** ``text`` is a text content
of the element.

**Async:** no.

It tries to return the value of the following JavaScript ``Node`` properties:

* textContent
* innerText
* value

If all of them are empty an empty string is returned.


.. _splash-element-info:

element:info
------------

Get useful information about the element.

**Signature:** ``info = element:info()``

**Returns:** ``info`` is a table with element info.

**Async:** no.

Info is a table with the following fields:

* nodeName - node name in a lower case (e.g. *h1*)
* attributes - table with attributes names and its values
* tag - html string representation of the element
* html - inner html of the element
* text - inner text of the element
* x - x coordinate of the element
* y - y coordinate of the element
* width - width of the element
* height - height of the element
* visible - flag representing if the element is visible


.. _splash-element-field-value:

element:field_value
-------------------

Get value of the field element (input, select).

**Signature:** ``ok, info = element:field_value()``

**Returns:** ``ok, value`` pair. If ``ok`` is nil then error happened during the function call;
``value`` provides an information about error type; otherwise ``value`` is a value of the
element.

**Async:** no.

The value can be a
* string - for text/radio input and select and other element types
* array of strings - for multi select
* boolean - for checkbox input


.. _splash-element-form-values:

element:form_values
-------------------

Return a table with form values if the element type is *form*

**Signature:** ``ok, info = element:form_values()``

**Returns:** ``ok, values`` pair. If ``ok`` is nil then error happened during the function call
or node type is not *form*; ``values`` provides an information about error type; otherwise
``values`` is a table of values.

**Async:** no.


.. _splash-element-fill:

element:fill
------------

Fill the form with the provided values

**Signature:** ``ok, reason = element:fill(values)``

**Parameters:**

* values - table with input names as keys and values as input values

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during the
function call; ``reason`` provides an information about error type.

**Async:** no.

In order to fill your form your inputs must have ``name`` property and this method will
select those input using that property.

Example of filling the following form:

.. code-block:: html

    <form id="login">
        <input type="text" name="username" />
        <input type="password" name="password" />
    </form>

.. code-block:: lua

    function main(splash)
        assert(splash:select('.login'):fill({ username="admin", password="pass" }))
    end


.. _splash-element-send-keys:

element:send_keys
-----------------

Send keyboard events to the element.

**Signature:** ``ok = element:send_keys(keys)``

**Parameters**

* keys - string representing the keys to be sent as keyboard events.

**Returns:** ``ok`` pair. If ``ok`` is nil then error happened during the function call.

**Async:** no.

This methods do the following:

* clicks on the element
* send the specified keyboard events

See more about keyboard events in in :ref:`splash-send-keys`.


.. _splash-element-send-text:

element:send_text
-----------------

Send keyboard events to the element.

**Signature:** ``ok = element:send_text(text)``

**Parameters**

* text - string to be sent as input.

**Returns:** ``ok`` pair. If ``ok`` is nil then error happened during the function call.

**Async:** no.

This methods do the following:

* clicks on the element
* send the specified text to the element

See more about it in :ref:`splash-send-text`.



.. _splash-element:

Element Object
==============

Element objects are instanced by :ref:`splash-select`;

.. _splash-element-attributes:

Attributes
~~~~~~~~~~

The following fields are read-only.

.. _splash-element-id:

element.id
----------

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

Check whether the element exists in DOM. If the element doesn't exist almost all other
methods will fail.

**Signature:** ``exists = element:exists()``

**Returns:** ``exists`` indicated whether the element exists.

**Async:** no.


.. _splash-node-property:

element:node_property
---------------------

Return the value of the specified property of the element

**Signature:** ``ok, value = element:node_property(property_name)``

**Parameters:**

* property_name - name of the node property

**Returns:** ``ok, value`` pair. If ``ok`` is nil then error happened during the function
call; ``value`` provides an information about error type; otherwise ``value`` is a value of
the specified property

**Async:** no.


.. _splash-node-method:

element:node_method
-------------------

Return the callable Lua function which call the specified node method.

**Signature:** ``ok, method = element:node_method(method_name)``

**Parameters:**

* method_name - name of the node method

**Returns:** ``ok, method`` pair. If ``ok`` is nil then error happened during the function
call; ``method`` provides an information about error type; otherwise ``value`` is a function
that can be called from Lua to execute node method in page context.

**Async:** no.

See more in :ref:`splash-jsfunc`.

.. note::

    If the specified method returns another HTML element it will be represented as a table with
    ``type`` property which equals to ``'node'``


.. _splash-element-mouse-click:

element:mouse_click
-------------------

Trigger mouse click event on the top-left corner of the element.

**Signature:** ``ok, reason = element:mouse_click()``

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during the
function call; ``reason`` provides an information about error type.

**Async:** no.

See more about mouse events in :ref:`splash-mouse-click`.


.. _splash-element-mouse-hover:

element:mouse_click
-------------------

Trigger mouse hover (JavaScript mouseover) event on the top-left corner of the element.

**Signature:** ``ok, reason = element:mouse_hover()``

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during the
function call; ``reason`` provides an information about error type.

**Async:** no.

See more about mouse events in :ref:`splash-mouse-click`.


.. _splash-element-get-styles:

element:get_styles
------------------

Return the computed styles of the element.

**Signature:** ``ok, styles = element:get_styles()``

**Returns:** ``ok, styles`` pair. If ``ok`` is nil then error happened during the
function call; ``styles`` provides an information about error type; otherwise
``styles`` is a table with computed styles of the element.

**Async:** no.

Example of getting the font size of the element.

.. code-block:: lua

    function main(splash)
        local element = splash:select('.element')
        local ok, styles = assert(element:get_styles())

        return styles['font-size']
    end


.. _splash-element-get-bounds:

element:get_bounds
------------------

Return the bounding client rectangle of the element

**Signature:** ``ok, styles = element:get_bounds()``

**Returns:** ``ok, bounds`` pair. If ``ok`` is nil then error happened during the
function call; ``bounds`` provides an information about error type; otherwise
``bounds`` is a table with the client bounding rectangle with the ``top``, ``right``,
``bottom`` and ``left`` coordinates.

**Async:** no.

Example of getting the bounds of the element.

.. code-block:: lua

    function main(splash)
        local element = splash:select('.element')
        local ok, bounds = assert(element:get_bounds())
        -- e.g. bounds is { top = 10, right = 20, bottom = 20, left = 10 }
        return bounds
    end


.. _splash-element-png:

element:png
-----------

Return a screenshot of the element in PNG format

**Signature:** ``ok, shot = element:png{width=nil, height=nil, scale_method='raster'}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``;

**Returns:** ``ok, shot`` pair. If ``ok`` is nil then error happened during the
function call; ``shot`` provides an information about error type; otherwise
``shot`` is a PNG screenshot data, as a :ref:`binary object <binary-objects>`.
When the result is empty (e.g. if the element is not visible) ``nil`` is returned.

**Async:** no.

See more in :ref:`splash-png`.



.. _splash-element-jpeg:

element:jpeg
------------

Return a screenshot of the element in JPEG format

**Signature:** ``ok, shot = element:jpeg{width=nil, height=nil, scale_method='raster', quality=75, region=nil}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``;
* quality - optional, quality of JPEG image, integer in range from ``0`` to ``100``;

**Returns:** ``ok, shot`` pair. If ``ok`` is nil then error happened during the
function call; ``shot`` provides an information about error type; otherwise
``shot`` is a JPEG screenshot data, as a :ref:`binary object <binary-objects>`.
When the result is empty (e.g. if the element is not visible) ``nil`` is returned.

**Async:** no.

See more in :ref:`splash-jpeg`.


.. _splash-element-visible:

element:visible
---------------

Check whether the element is visible.

**Signature:** ``ok, visible = element:visible()``

**Returns:** ``ok, visible`` pair. If ``ok`` is nil then error happened during the function
call; ``visible`` provides an information about error type; otherwise ``visible`` indicated whether
the element is visible.

**Async:** no.


.. _splash-element-fetch-text:

element:fetch_text
------------------

Fetch a text information from the element

**Signature:** ``ok, visible = element:fetch_text()``

**Returns:** ``ok, text`` pair. If ``ok`` is nil then error happened during the function call;
``text`` provides an information about error type; otherwise ``text`` is a text content
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

**Signature:** ``ok, info = element:info()``

**Returns:** ``ok, info`` pair. If ``ok`` is nil then error happened during the function call;
``info`` provides an information about error type; otherwise ``info`` is a table with info.

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


.. _splash-field-value:

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


.. _splash-form-values:

element:form_values
-------------------

Return a table with form values if the element type is *form*

**Signature:** ``ok, info = element:form_values()``

**Returns:** ``ok, values`` pair. If ``ok`` is nil then error happened during the function call
or node type is not *form*; ``values`` provides an information about error type; otherwise
``values`` is a table of values.

**Async:** no.


.. _splash-send-keys:

element:send_keys
-----------------

Send keyboard events to the element.

**Signature:** ``ok = element:send_keys(keys)``

**Parameters**

* keys - string representing the keys to be sent as keyboard events.

**Returns:** ``ok`` pair. If ``ok`` is nil then error happened during the function call.

**Async:** no.

This methods do the following:

* checks whether the selected element is editable
* clicks on the element
* send the specified keyboard events

See more about keyboard events in in :ref:`splash-send-keys`.


.. _splash-send-text:

element:send_text
-----------------

Send keyboard events to the element.

**Signature:** ``ok = element:send_text(text)``

**Parameters**

* text - string to be sent as input.

**Returns:** ``ok`` pair. If ``ok`` is nil then error happened during the function call.

**Async:** no.

This methods do the following:

* checks whether the selected element is editable
* clicks on the element
* send the specified text to the element

See more about it in :ref:`splash-send-text`.



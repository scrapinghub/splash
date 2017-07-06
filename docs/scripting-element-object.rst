.. _splash-element:

Element Object
==============

Element objects wrap JavaScript DOM nodes. They are created whenever some
method returns any type of DOM node (Node, Element, HTMLElement, etc).

:ref:`splash-select` and :ref:`splash-select-all` return element objects;
:ref:`splash-evaljs` may also return element objects, but currently they
can't be inside other objects or arrays - only top-level Node and NodeList
is supported.

Methods
~~~~~~~

To modify or retrieve information about the element you can use the
following methods.

.. _splash-element-mouse-click:

element:mouse_click
-------------------

Trigger mouse click event on the element.

**Signature:** ``ok, reason = element:mouse_click{x=nil, y=nil}``

**Parameters:**

* x - optional, x coordinate relative to the left corner of the element
* y - optional, y coordinate relative to the top corner of the element

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
the function call; ``reason`` provides an information about error type.

**Async:** yes.

If x or y coordinate is not provided, they are set to width/2 and height/2
respectively, and the click is triggered on the middle of the element.

Coordinates can have a negative value which means the click will be triggered
outside of the element.

Example 1: click inside element, but closer to the top left corner:

.. code-block:: lua

    function main(splash)
        -- ...
        local element = splash:select('.element')
        local bounds = element:bounds()
        assert(element:mouse_click{x=bounds.width/3, y=bounds.height/3})
        -- ...
    end


Example 2: click on the area above the element by 10 pixels

.. code-block:: lua

    function main(splash)
        -- ...
        splash:set_viewport_full()
        local element = splash:select('.element')
        assert(element:mouse_click{y=-10})
        -- ...
    end

Unlike :ref:`splash-mouse-click`, :ref:`splash-element-mouse-click` waits
until clicking is done, so to see consequences of click reflected in a page
there is no need to call :ref:`splash-wait`.

If an element is outside the current viewport, viewport is scrolled to make
element visible. If scrolling was necessary, page is not scrolled back
to the original position after the click.

See more about mouse events in :ref:`splash-mouse-click`.

.. _splash-element-mouse-hover:

element:mouse_hover
-------------------

Trigger mouse hover (JavaScript mouseover) event on the element.

**Signature:** ``ok, reason = element:mouse_hover{x=0, y=0}``

**Parameters:**

* x - optional, x coordinate relative to the left corner of the element
* y - optional, y coordinate relative to the top corner of the element

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened
during the function call; ``reason`` provides an information about error type.

**Async:** no.

If x or y coordinate is not provided, they are set to width/2 and height/2
respectively, and the hover is triggered on the middle of the element.

Coordinates can have a negative value which means the hover will be
triggered outside of the element.

Example 1: mouse hover over top left element corner:

.. code-block:: lua

    function main(splash)
        -- ...
        local element = splash:select('.element')
        assert(element:mouse_hover{x=0, y=0})
        -- ...
    end


Example 2: hover over the area above the element by 10 pixels

.. code-block:: lua

    function main(splash)
        -- ...
        splash:set_viewport_full()
        local element = splash:select('.element')
        assert(element:mouse_hover{y=-10})
        -- ...
    end

Unlike :ref:`splash-mouse-hover`, :ref:`splash-element-mouse-hover` waits
until event is propagated, so to see consequences of click reflected in a page
there is no need to call :ref:`splash-wait`.

If an element is outside the current viewport, viewport is scrolled to make
element visible. If scrolling was necessary, page is not scrolled back
to the original position.

See more about mouse events in :ref:`splash-mouse-hover`.


.. _splash-element-styles:

element:styles
--------------

Return the computed styles of the element.

**Signature:** ``styles = element:styles()``

**Returns:** ``styles`` is a table with computed styles of the element.

**Async:** no.

This method returns the result of JavaScript `window.getComputedStyle()`_
applied on the element.

Example: get all computed styles and return the ``font-size`` property.

.. code-block:: lua

    function main(splash)
        -- ...
        local element = splash:select('.element')
        return element:styles()['font-size']
    end


.. _window.getComputedStyle(): https://developer.mozilla.org/en-US/docs/Web/API/Window/getComputedStyle

.. _splash-element-bounds:

element:bounds
--------------

Return the bounding client rectangle of the element

**Signature:** ``bounds = element:bounds()``

**Returns:** ``bounds`` is a table with the client bounding rectangle
with the ``top``, ``right``, ``bottom`` and ``left`` coordinates and
also with ``width`` and ``height`` values.

**Async:** no.

Example: get the bounds of the element.

.. code-block:: lua

    function main(splash)
        -- ..
        local element = splash:select('.element')
        return element:bounds()
        -- e.g. bounds is { top = 10, right = 20, bottom = 20, left = 10, height = 10, width = 10 }
    end


.. _splash-element-png:

element:png
-----------

Return a screenshot of the element in PNG format

**Signature:** ``shot = element:png{width=nil, scale_method='raster', pad=0}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``;
* pad - optional, integer or ``{left, top, right, bottom}`` values of padding

**Returns:** ``shot`` is a PNG screenshot data, as
a :ref:`binary object <binary-objects>`. When the result is empty
(e.g. if the element doesn't exist in DOM or it isn't visible) ``nil``
is returned.

**Async:** no.

*pad* parameter sets the padding of the resulting image. If it is
a single integer then the padding from all sides will be equal.
If the value of the padding is positive the resulting screenshot
will be expanded by the specified amount of pixes. And if the value
of padding is negative the resulting screenshot will be shrunk by the
specified amount of pixels.

Example: return a padded screenshot of the element

.. code-block:: lua

    function main(splash)
        -- ..
        local element = splash:select('.element')
        return element:png{pad=10}
    end

If an element is not in a viewport, viewport temporarily scrolls
to make the element visible, then it scrolls back.

See more in :ref:`splash-png`.


.. _splash-element-jpeg:

element:jpeg
------------

Return a screenshot of the element in JPEG format

**Signature:** ``shot = element:jpeg{width=nil, scale_method='raster', quality=75, region=nil, pad=0}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``;
* quality - optional, quality of JPEG image, integer in range from
  ``0`` to ``100``;
* pad - optional, integer or ``{left, top, right, bottom}`` values of padding

**Returns:** ``shot`` is a JPEG screenshot data, as
a :ref:`binary object <binary-objects>`. When the result is empty (e.g. if
the element doesn't exist in DOM or it isn't visible) ``nil`` is returned.

**Async:** no.

*pad* parameter sets the padding of the resulting image. If it is a single
integer then the padding from all sides will be equal. If the value of the
padding is positive the resulting screenshot will be expanded by the
specified amount of pixes. And if the value of padding is negative the resulting
screenshot will be shrunk by the specified amount of pixes.

If an element is not in a viewport, viewport temporarily scrolls
to make the element visible, then it scrolls back.

See more in :ref:`splash-jpeg`.


.. _splash-element-visible:

element:visible
---------------

Check whether the element is visible.

**Signature:** ``visible = element:visible()``

**Returns:** ``visible`` indicates whether the element is visible.

**Async:** no.


.. _splash-element-focused:

element:focused
---------------

Check whether the element has focus.

**Signature:** ``focused = element:focused()``

**Returns:** ``focused`` indicates whether the element is focused.

**Async:** no.


.. _splash-element-text:

element:text
------------

Fetch a text information from the element

**Signature:** ``text = element:text()``

**Returns:** ``text`` is a text content
of the element.

**Async:** no.

It tries to return the trimmed value of the following JavaScript
``Node`` properties:

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

Get value of the field element (input, select, textarea, button).

**Signature:** ``ok, value = element:field_value()``

**Returns:** ``ok, value`` pair. If ``ok`` is nil then error happened
during the function call; ``value`` provides an information about error type.
When there is no error ``ok`` is true and ``value`` is a value of the element.

**Async:** no.

This method works in the following way:

    - if the element type is ``select``:
        - if the ``multiple`` attribute is ``true`` it returns a *table*
          with the selected values;
        - otherwise it returns the value of the select;
    - if the element has attribute ``type="radio"``:
        - if it's checked returns its value;
        - other it returns ``nil``
    - if the element has attribute ``type="checkbox"`` it returns *bool* value
    - otherwise it returns the value of the ``value`` attribute or
      *empty string* if it doesn't exist


.. _splash-element-form-values:

element:form_values
-------------------

Return a table with form values if the element type is *form*

**Signature:** ``form_values, reason = element:form_values{values='auto'}``

**Parameters:**

* values - type of the return value, can be one of
  ``'auto'``, ``'list'`` or ``'first'``

**Returns:** ``form_values, reason`` pair. If ``form_values`` is nil then
error happened during the function call or node type is not *form*;
``reason`` provides an information about error type; otherwise
``form_values`` is a table with element names as keys and values as values.

**Async:** no.

The returned values depend on ``values`` parameter. It can be in 3 states:

``'auto'``
    Returned values are tables or singular values depending on the
    form element type:

    - if the element is ``<select multiple>`` the returned value is
      a table with the selected option values or text contents if the value
      attribute is missing;
    - if the form has several elements with the same ``name`` attribute the
      returned value is a table with all values of that elements;
    - otherwise it is a string (for text and radio inputs), bool (for checkbox
      inputs) or ``nil`` the value of ``value`` attribute.

    This result type is convenient if you're working with the result in a Lua
    script.

``'list'``
    Returned values always are tables (lists), even if the form element
    can be a singular value, useful for forms with unknown structure. Few notes:

    - if the element is a checkbox input and a ``value`` attribute then
      the table will contain that value;
    - if the element is ``<select multiple>`` and they are several of them
      with the same names then their values will be concatenated with the
      previous ones

    This result type is convenient if you're writing generic form-handling
    code - unlike ``auto`` there is no need to support multiple data types.

``'first'``
    Returned values always are singular values, even if the form element
    can multiple value. If the element has multiple values only the *first*
    one will be selected.

Example 1: return the values of the following login form

.. code-block:: html

    <form id="login">
        <input type="text" name="username" value="admin" />
        <input type="password" name="password" value="pass" />
        <input type="checkbox" name="remember" value="yes" checked />
    </form>

.. code-block:: lua

    function main(splash)
        -- ...
        local form = splash:select('#login')
        return assert(form:form_values())
    end

    -- returned values are
    { username = 'admin', password = 'pass', remember = true }


Example 2: when ``values`` is equal to ``'list'``

.. code-block:: lua

    function main(splash)
        -- ...
        local form = splash:select('#login')
        return assert(form:form_values{values='list'}))
    end

    -- returned values are
    { username = ['admin'], password = ['pass'], remember = ['checked'] }

Example 3: return the values of the following form when ``values``
is equal to ``'first'``

.. code-block:: html

    <form>
        <input type="text" name="foo[]" value="coffee"/>
        <input type="text" name="foo[]" value="milk"/>
        <input type="text" name="foo[]" value="eggs"/>
        <input type="text" name="baz" value="foo"/>
        <input type="radio" name="choice" value="yes"/>
        <input type="radio" name="choice" value="no" checked/>
        <input type="checkbox" name="check" checked/>

        <select multiple name="selection">
            <option value="1" selected>1</option>
            <option value="2">2</option>
            <option value="3" selected>2</option>
        </select>
    </form>

.. code-block:: lua

    function main(splash)
        -- ...
        local form = splash:select('form')
        return assert(form:form_values(false))
    end

    -- returned values are
    {
        ['foo[]'] = 'coffee',
        baz = 'foo',
        choice = 'no',
        check = false,
        selection = '1'
    }


.. _splash-element-fill:

element:fill
------------

Fill the form with the provided values

**Signature:** ``ok, reason = element:fill(values)``

**Parameters:**

* values - table with input names as keys and values as input values

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
the function call; ``reason`` provides an information about error type.

**Async:** no.

In order to fill your form your inputs must have ``name`` property and
this method will select those input using that property.

Example 1: get the current values, change password and fill the form

.. code-block:: html

    <form id="login">
        <input type="text" name="username" value="admin" />
        <input type="password" name="password" value="pass" />
    </form>

.. code-block:: lua

    function main(splash)
        -- ...
        local form = splash:select('#login')
        local values = assert(form:form_values())
        values.password = "l33t"
        assert(form:fill(values))
    end

Example 2: fill more complex form

.. code-block:: html

    <form id="signup" action="/signup">
        <input type="text" name="name"/>
        <input type="radio" name="gender" value="male"/>
        <input type="radio" name="gender" value="female"/>

        <select multiple name="hobbies">
            <option value="sport">Sport</option>
            <option value="cars">Cars</option>
            <option value="games">Video Games</option>
        </select>

        <button type="submit">Sign Up</button>
    </form>


.. code-block:: lua

    function main(splash)
      assert(splash:go(splash.args.url))
      assert(splash:wait(0.1))

      local form = splash:select('#signup')
      local values = {
        name = 'user',
        gender = 'female',
        hobbies = {'sport', 'games'},
      }

      assert(form:fill(values))
      assert(form:submit())
      -- ...
    end


.. _splash-element-send-keys:

element:send_keys
-----------------

Send keyboard events to the element.

**Signature:** ``ok, reason = element:send_keys(keys)``

**Parameters**

* keys - string representing the keys to be sent as keyboard events.

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
the function call; ``reason`` provides an information about error type.

**Async:** no.

This method does the following:

* clicks on the element
* send the specified keyboard events

See more about keyboard events in in :ref:`splash-send-keys`.


.. _splash-element-send-text:

element:send_text
-----------------

Send keyboard events to the element.

**Signature:** ``ok, reason = element:send_text(text)``

**Parameters**

* text - string to be sent as input.

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
the function call; ``reason`` provides an information about error type.

**Async:** no.

This method does the following:

* clicks on the element
* send the specified text to the element

See more about it in :ref:`splash-send-text`.


.. _splash-element-submit:

element:submit
--------------

Submit the form element.

**Signature:** ``ok, reason = element:submit()``

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
the function call (e.g. you are trying to submit on element which is not
a form); ``reason`` provides an information about error type.

**Async:** no.

Example: get the form, fill with values and submit it

.. code-block:: html

    <form id="login" action="/login">
        <input type="text" name="username" />
        <input type="password" name="password" />
        <input type="checkbox" name="remember" />
        <button type="submit">Submit</button>
    </form>

.. code-block:: lua

    function main(splash)
        -- ...
        local form = splash:select('#login')
        assert(form:fill({ username='admin', password='pass', remember=true }))
        assert(form:submit())
        -- ...
    end

.. _splash-element-exists:

element:exists
--------------

Check whether the element exists in DOM. If the element doesn't exist
some of the methods will fail, returning the error flag.

**Signature:** ``exists = element:exists()``

**Returns:** ``exists`` indicated whether the element exists.

**Async:** no.

.. note::

    **Don't use** ``splash:select(..):exists()`` to check
    if an element is present - :ref:`splash-select` returns ``nil``
    if selector returns nothing. Check for ``nil`` instead.

    ``element:exists()`` should only be used if you already have
    an Element instance, but suspect it can be removed from the current DOM.

There are several reasons why the element can be absent from DOM.
One of the reasons is that the element was removed by some JavaScript code.


Example 1: the element was removed by JS code

.. code-block:: lua

    function main(splash)
        -- ...
        local element = splash:select('.element')
        assert(splash:runjs('document.write("<body></body>")'))
        assert(splash:wait(0.1))
        local exists = element:exists() -- exists will be `false`
        -- ...
    end

Another reason is that the element was created by script and not inserted
into DOM.

Example 2: the element is not inserted into DOM

.. code-block:: lua

    function main(splash)
        -- ...
        local element = splash:select('.element')
        local cloned = element.node:cloneNode() -- the cloned element isn't in DOM
        local exists = cloned:exists() -- exists will be `false`
        -- ...
    end


.. _splash-element-dom-methods:

DOM Methods
~~~~~~~~~~~

In addition to custom Splash-specific methods Element supports many
common DOM HTMLElement methods.

Usage
-----

To use these methods just call them on ``element``. For example, to check
if an element has a specific attribute you can use hasAttribute_ method:

.. code-block:: lua

    function main(splash)
        -- ...
        if splash:select('.element'):hasAttribute('foo') then
            -- ...
        end
        -- ...
    end


.. _hasAttribute: https://developer.mozilla.org/en-US/docs/Web/API/Element/hasAttribute

Another example: to make sure element is in a viewport, you can call its
``scrollIntoViewIfNeeded`` method:

.. code-block:: lua

    function main(splash)
        -- ...
        splash:select('.element'):scrollIntoViewIfNeeded()
        -- ...
    end

Supported DOM methods
---------------------

Methods inherited from EventTarget_:
    - addEventListener
    - removeEventListener

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
    - scrollIntoViewIfNeeded
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

These methods should work as their JS counterparts, but in Lua.

For example, you can attach event handlers using
``element:addEventListener(event, listener)``.

.. code-block:: lua

    function main(splash)
        -- ...
        local element = splash:select('.element')
        local x, y = 0, 0

        local store_coordinates = function(event)
            x = event.clientX
            y = event.clientY
        end

        element:addEventListener('click', store_coordinates)
        assert(splash:wait(10))
        return x, y
    end


.. _HTMLElement: https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement
.. _Element: https://developer.mozilla.org/en-US/docs/Web/API/Element
.. _Node: https://developer.mozilla.org/en-US/docs/Web/API/Node
.. _Event: https://developer.mozilla.org/en-US/docs/Web/API/Event
.. _EventTarget: https://developer.mozilla.org/en-US/docs/Web/API/EventTarget


.. _splash-element-attributes:

Attributes
~~~~~~~~~~

.. _splash-element-node:

element.node
------------

``element.node`` has all exposed element DOM methods and attributes available,
but not custom Splash methods and attributes. Use it for readability if
you want to be more explicit. It also allows to avoid possible naming
conflicts in future.

For example, to get element's innerHTML one can use ``.node.innerHTML``:

.. code-block:: lua

    function main(splash)
        -- ...
        return {html=splash:select('.element').node.innerHTML}
    end

.. _splash-element-inner_id:

element.inner_id
----------------

ID of the inner representation of the element, read-only.
It may be useful for comparing element instances for the equality.

Example:

.. code-block:: lua

    function main(splash)
        -- ...

        local same = element2.inner_id == element2.inner_id

        -- ...
    end

.. _splash-element-dom-attributes:

DOM Attributes
~~~~~~~~~~~~~~

Usage
-----

Element objects also provide almost all DOM element attributes.
For example, get element's node name (p, div, a, etc.):

.. code-block:: lua

    function main(splash)
        -- ...
        local tag_name = splash:select('.foo').nodeName
        -- ...
    end

Many of attributes are writable, not only readable - you can e.g.
set innerHTML of an element:

.. code-block:: lua

    function main(splash)
        -- ...
        splash:select('.foo').innerHTML = "hello"
        -- ...
    end

Supported DOM attributes
------------------------

The list of supported properties (some of them are mutable, other
are read-only):

Properties inherited from HTMLElement_:
    - accessKey
    - accessKeyLabel *(read-only)*
    - contentEditable
    - isContentEditable *(read-only)*
    - dataset *(read-only)*
    - dir
    - draggable
    - hidden
    - lang
    - offsetHeight *(read-only)*
    - offsetLeft *(read-only)*
    - offsetParent *(read-only)*
    - offsetTop *(read-only)*
    - spellcheck
    - style - a table with styles which can be modified
    - tabIndex
    - title
    - translate

Properties inherited from Element_:
    - attributes *(read-only)* - a table with attributes of the element
    - classList *(read-only)* - a table with class names of the element
    - className
    - clientHeight *(read-only)*
    - clientLeft *(read-only)*
    - clientTop *(read-only)*
    - clientWidth *(read-only)*
    - id
    - innerHTML
    - localeName *(read-only)*
    - namespaceURI *(read-only)*
    - nextElementSibling *(read-only)*
    - outerHTML
    - prefix *(read-only)*
    - previousElementSibling *(read-only)*
    - scrollHeight *(read-only)*
    - scrollLeft
    - scrollTop
    - scrollWidth *(read-only)*
    - tabStop
    - tagName *(read-only)*

Properties inherited from Node_:
    - baseURI *(read-only)*
    - childNodes *(read-only)*
    - firstChild *(read-only)*
    - lastChild *(read-only)*
    - nextSibling *(read-only)*
    - nodeName *(read-only)*
    - nodeType *(read-only)*
    - nodeValue
    - ownerDocument *(read-only)*
    - parentNode *(read-only)*
    - parentElement *(read-only)*
    - previousSibling *(read-only)*
    - rootNode *(read-only)*
    - textContent

Also, you can attach event handlers to the specified event. When the handler
is called it will receive ``event`` table with the almost all available
methods and properties.

.. code-block:: lua

    function main(splash)
        -- ...
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

Use ``element:addEventListener()`` method if you want to attach multiple event
handlers for an event.

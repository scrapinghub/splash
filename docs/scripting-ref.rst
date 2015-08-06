.. _scripting-reference:

Splash Scripts Reference
========================

.. warning::

    Scripting support is an experimental feature for early adopters;
    API could change in future releases.

``splash`` object is passed to ``main`` function; via this object
a script can control the browser. Think of it as of an API to
a single browser tab.

.. _splash-go:

splash:go
---------

Go to an URL. This is similar to entering an URL in a browser
address bar, pressing Enter and waiting until page loads.

**Signature:** ``ok, reason = splash:go{url, baseurl=nil, headers=nil}``

**Parameters:**

* url - URL to load;
* baseurl - base URL to use, optional. When ``baseurl`` argument is passed
  the page is still loaded from ``url``, but it is rendered as if it was
  loaded from ``baseurl``: relative resource paths will be relative
  to ``baseurl``, and the browser will think ``baseurl`` is in address bar;
* headers - a Lua table with HTTP headers to add/replace in the initial request.

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
page load; ``reason`` provides an information about error type.

**Async:** yes, unless the navigation is locked.

Four types of errors are reported (``ok`` can be ``nil`` in 4 cases):

1. There is a network error: a host doesn't exist, server dropped connection,
   etc. In this case ``reason`` is ``"network<code>"``. A list of possible
   error codes can be found in `Qt docs`_. For example, ``"network3"`` means
   a DNS error (invalid hostname).
2. Server returned a response with 4xx or 5xx HTTP status code.
   ``reason`` is ``"http<code>"`` in this case, i.e. for
   HTTP 404 Not Found ``reason`` is ``"http404"``.
3. Navigation is locked (see :ref:`splash-lock-navigation`); ``reason``
   is ``"navigation_locked"``.
4. If Splash can't decide what caused the error, just ``"error"`` is returned.

.. _Qt docs: http://doc.qt.io/qt-5/qnetworkreply.html#NetworkError-enum

Error handling example:

.. code-block:: lua

    local ok, reason = splash:go("http://example.com")
    if not ok then
        if reason:sub(0,4) == 'http' then
            -- handle HTTP errors
        else
            -- handle other errors
        end
    end
    -- process the page

    -- assert can be used as a shortcut for error handling
    assert(splash:go("http://example.com"))

Errors (ok==nil) are only reported when "main" webpage request failed.
If a request to a related resource failed then no error is reported by
``splash:go``. To detect and handle such errors (e.g. broken image/js/css
links, ajax requests failed to load) use :ref:`splash-har`.

``splash:go`` follows all HTTP redirects before returning the result,
but it doesn't follow HTML ``<meta http-equiv="refresh" ...>`` redirects or
redirects initiated by JavaScript code. To give the webpage time to follow
those redirects use :ref:`splash-wait`.

``headers`` argument allows to add or replace default HTTP headers for the
initial request. To set custom headers for all further requests
(including requests to related resources) use
:ref:`splash-set-custom-headers` or :ref:`splash-on-request`.

Custom headers example:

.. code-block:: lua

    local ok, reason = splash:go{"http://example.com", headers={
        ["Custom-Header"] = "Header Value",
    }})

User-Agent header is special: once used, it is kept for further requests.
This is an implementation detail and it could change in future releases;
to set User-Agent header it is recommended to use
:ref:`splash-set-user-agent` method.

.. _splash-wait:

splash:wait
-----------

Wait for ``time`` seconds. When script is waiting WebKit continues
processing the webpage.

**Signature:** ``ok, reason = splash:wait{time, cancel_on_redirect=false, cancel_on_error=true}``

**Parameters:**

* time - time to wait, in seconds;
* cancel_on_redirect - if true (not a default) and a redirect
  happened while waiting, then ``splash:wait`` stops earlier and returns
  ``nil, "redirect"``. Redirect could be initiated by
  ``<meta http-equiv="refresh" ...>`` HTML tags or by JavaScript code.
* cancel_on_error - if true (default) and an error which prevents page
  from being rendered happened while waiting (e.g. an internal WebKit error
  or a network error like a redirect to a non-resolvable host)
  then ``splash:wait`` stops earlier and returns ``nil, "<error string>"``.

**Returns:** ``ok, reason`` pair. If ``ok`` is ``nil`` then the timer was
stopped prematurely, and ``reason`` contains a string with a reason.

**Async:** yes.

Usage example:

.. code-block:: lua

     -- go to example.com, wait 0.5s, return rendered html, ignore all errors.
     function main(splash)
         splash:go("http://example.com")
         splash:wait(0.5)
         return {html=splash:html()}
     end

By default wait timer continues to tick when redirect happens.
``cancel_on_redirect`` option can be used to restart the timer after
each redirect. For example, here is a function that waits for a given
time after each page load in case of redirects:

.. code-block:: lua

    function wait_restarting_on_redirects(splash, time, max_redirects)
        local redirects_remaining = max_redirects
        while redirects_remaining do
            local ok, reason = self:wait{time=time, cancel_on_redirect=true}
            if reason ~= 'redirect' then
                return ok, reason
            end
            redirects_remaining = redirects_remaining - 1
        end
        return nil, "too_many_redirects"
    end


.. _splash-jsfunc:

splash:jsfunc
-------------

Convert JavaScript function to a Lua callable.

**Signature:** ``lua_func = splash:jsfunc(func)``

**Parameters:**

* func - a string which defines a JavaScript function.

**Returns:** a function that can be called from Lua to execute JavaScript
code in page context.

**Async:** no.

Example:

.. code-block:: lua

    function main(splash)
        local get_div_count = splash:jsfunc([[
            function (){
                var body = document.body;
                var divs = body.getElementsByTagName('div');
                return divs.length;
            }
        ]])

        splash:go(splash.args.url)
        return get_div_count()
    end

Note how Lua ``[[ ]]`` string syntax is helpful here.

JavaScript functions may accept arguments:

.. code-block:: lua

    local vec_len = splash:jsfunc([[
        function(x, y) {
           return Math.sqrt(x*x + y*y)
        }
    ]])
    return {res=vec_len(5, 4)}

Global JavaScript functions can be wrapped directly:

.. code-block:: lua

    local pow = splash:jsfunc("Math.pow")
    local twenty_five = pow(5, 2)  -- 5^2 is 25
    local thousand = pow(10, 3)    -- 10^3 is 1000

Lua strings, numbers, booleans and tables can be passed as arguments;
they are converted to JS strings/numbers/booleans/objects.
Currently it is not possible to pass other Lua objects. For example, it
is not possible to pass a wrapped JavaScript function or a regular Lua function
as an argument to another wrapped JavaScript function.

.. _lua-js-conversion-rules:

Lua → JavaScript conversion rules:

==============  =================
Lua             JavaScript
==============  =================
string          string
number          number
boolean         boolean
table           Object
nil             undefined
==============  =================

Function result is converted from JavaScript to Lua data type. Only simple
JS objects are supported. For example, returning a function or a
JQuery selector from a wrapped function won't work.

.. _js-lua-conversion-rules:

JavaScript → Lua conversion rules:

==============  =================
JavaScript      Lua
==============  =================
string          string
number          number
boolean         boolean
Object          table
Array           table
``undefined``   ``nil``
``null``        ``""`` (an empty string)
Date            string: date's ISO8601 representation, e.g. ``1958-05-21T10:12:00Z``
RegExp          table ``{_jstype='RegExp', caseSensitive=true/false, pattern='my-regexp'}``
function        an empty table ``{}`` (don't rely on it)
==============  =================

Function arguments and return values are passed by value. For example,
if you modify an argument from inside a JavaScript function then the caller
Lua code won't see the changes, and if you return a global JS object and modify
it in Lua then object won't be changed in webpage context.

.. note::

    The rule of thumb: if an argument or a return value can be serialized
    via JSON, then it is fine.

If a JavaScript function throws an error, it is re-throwed as a Lua error.
To handle errors it is better to use JavaScript try/catch because some of the
information about the error can be lost in JavaScript → Lua conversion.

See also: :ref:`splash-runjs`, :ref:`splash-evaljs`, :ref:`splash-wait-for-resume`,
:ref:`splash-autoload`.

.. _splash-evaljs:

splash:evaljs
-------------

Execute a JavaScript snippet in page context and return the result of the
last statement.

**Signature:** ``result = splash:evaljs(snippet)``

**Parameters:**

* snippet - a string with JavaScript source code to execute.

**Returns:** the result of the last statement in ``snippet``,
converted from JavaScript to Lua data types. In case of syntax errors or
JavaScript exceptions an error is raised.

**Async:** no.

JavaScript → Lua conversion rules are the same as for
:ref:`splash:jsfunc <js-lua-conversion-rules>`.

``splash:evaljs`` is useful for evaluation of short JavaScript snippets
without defining a wrapper function. Example:

.. code-block:: lua

    local title = splash:evaljs("document.title")

Don't use :ref:`splash-evaljs` when the result is not needed - it is
inefficient and could lead to problems; use :ref:`splash-runjs` instead.
For example, the following innocent-looking code (using jQuery) may fail:

.. code-block:: lua

    splash:evaljs("$(console.log('foo'));")

A gotcha is that to allow chaining jQuery ``$`` function returns a huge object,
:ref:`splash-evaljs` tries to serialize it and convert to Lua. It is a waste
of resources, and it could trigger internal protection measures;
:ref:`splash-runjs` doesn't have this problem.

If the code you're evaluating needs arguments it is better to use
:ref:`splash-jsfunc` instead of :ref:`splash-evaljs` and string formatting.
Compare:

.. code-block:: lua

    function main(splash)

        local font_size = splash:jsfunc([[
            function(sel) {
                var el = document.querySelector(sel);
                return getComputedStyle(el)["font-size"];
            }
        ]])

        local font_size2 = function(sel)
            -- FIXME: escaping of `sel` parameter!
            local js = string.format([[
                var el = document.querySelector("%s");
                getComputedStyle(el)["font-size"]
            ]], sel)
            return splash:evaljs(js)
        end

        -- ...
    end

See also: :ref:`splash-runjs`, :ref:`splash-jsfunc`,
:ref:`splash-wait-for-resume`, :ref:`splash-autoload`.

.. _splash-js-enabled:

splash.js_enabled
-----------------

Enable or disable execution of JavaSript code embedded in the page.

**Signature:** ``splash.js_enabled = true/false``

JavaScript execution is enabled by default.

.. _splash-runjs:

splash:runjs
------------

Run JavaScript code in page context.

**Signature:** ``ok, error = splash:runjs(snippet)``

**Parameters:**

* snippet - a string with JavaScript source code to execute.

**Returns:** ``ok, error`` pair. When the execution is successful
``ok`` is True. In case of JavaScript errors ``ok`` is ``nil``,
and ``error`` contains the error string.

**Async:** no.

Example:

.. code-block:: lua

    assert(splash:runjs("document.title = 'hello';"))

Note that JavaScript functions defined using ``function foo(){}`` syntax
**won't** be added to the global scope:

.. code-block:: lua

    assert(splash:runjs("function foo(){return 'bar'}"))
    local res = splash:evaljs("foo()")  -- this raises an error

It is an implementation detail: the code passed to :ref:`splash-runjs`
is executed in a closure. To define functions use global variables, e.g.:

.. code-block:: lua

    assert(splash:runjs("foo = function (){return 'bar'}"))
    local res = splash:evaljs("foo()")  -- this returns 'bar'

If the code needs arguments it is better to use :ref:`splash-jsfunc`.
Compare:

.. code-block:: lua

    function main(splash)

        -- Lua function to scroll window to (x, y) position.
        function scroll_to(x, y)
            local js = string.format(
                "window.scrollTo(%s, %s);",
                tonumber(x),
                tonumber(y)
            )
            assert(splash:runjs(js))
        end

        -- a simpler version using splash:jsfunc
        local scroll_to2 = splash:jsfunc("window.scrollTo")

        -- ...
    end

See also: :ref:`splash-runjs`, :ref:`splash-jsfunc`, :ref:`splash-autoload`,
:ref:`splash-wait-for-resume`.

.. _splash-wait-for-resume:

splash:wait_for_resume
----------------------

Run asynchronous JavaScript code in page context. The Lua script will
yield until the JavaScript code tells it to resume.

**Signature:** ``result, error = splash:wait_for_resume(snippet, timeout)``

**Parameters:**

* snippet - a string with a JavaScript source code to execute. This code
  must include a function called ``main``. The first argument to ``main``
  is an object that has the properties ``resume`` and ``error``. ``resume``
  is a function which can be used to resume Lua execution. It takes an optional
  argument which will be returned to Lua in the ``result.value`` return value.
  ``error`` is a function which can be called with a required string value
  that is returned in the ``error`` return value.
* timeout - a number which determines (in seconds) how long to allow JavaScript
  to execute before forceably returning control to Lua. Defaults to
  zero, which disables the timeout.

**Returns:** ``result, error`` pair. When the execution is successful
``result`` is a table. If the value returned by JavaScript is not
``undefined``, then the ``result`` table will contain a key ``value``
that has the value passed to ``splash.resume(…)``. The ``result`` table also
contains any additional key/value pairs set by ``splash.set(…)``. In case of
timeout or JavaScript errors ``result`` is ``nil`` and ``error`` contains an
error message string.

**Async:** yes.

Examples:

The first, trivial example shows how to transfer control of execution from Lua
to JavaScript and then back to Lua. This command will tell JavaScript to
sleep for 3 seconds and then return to Lua. Note that this is an async
operation: the Lua event loop and the JavaScript event loop continue to run
during this 3 second pause, but Lua will not continue executing the current
function until JavaScript calls ``splash.resume()``.

.. code-block:: lua

    function main(splash)

        local result, error = splash:wait_for_resume([[
            function main(splash) {
                setTimeout(function () {
                    splash.resume();
                }, 3000);
            }
        ]])

        -- result is {}
        -- error is nil

    end

``result`` is set to an empty table to indicate that nothing was returned
from ``splash.resume``. You can use ``assert(splash:wait_for_resume(…))``
even when JavaScript does not return a value because the empty table signifies
success to ``assert()``.

.. note::

    Your JavaScript code must contain a ``main()`` function. You will get an
    error if you do not include it. The first argument to this function can
    have any name you choose, of course. We will call it ``splash`` by
    convention in this documentation.

The next example shows how to return a value from JavaScript to Lua.
You can return booleans, numbers, strings, arrays, or objects.

.. code-block:: lua

    function main(splash)

        local result, error = splash:wait_for_resume([[
            function main(splash) {
                setTimeout(function () {
                    splash.resume([1, 2, 'red', 'blue']);
                }, 3000);
            }
        ]])

        -- result is {value={1, 2, 'red', 'blue'}}
        -- error is nil

    end

.. note::

    As with :ref:`splash-evaljs`, be wary of returning objects that are
    too large, such as the ``$`` object in jQuery, which will consume a lot
    of time and memory to convert to a Lua result.

You can also set additional key/value pairs in JavaScript with the
``splash.set(key, value)`` function. Key/value pairs will be included
in the ``result`` table returned to Lua. The following example demonstrates
this.

.. code-block:: lua

    function main(splash)

        local result, error = splash:wait_for_resume([[
            function main(splash) {
                setTimeout(function () {
                    splash.set("foo", "bar");
                    splash.resume("ok");
                }, 3000);
            }
        ]])

        -- result is {foo="bar", value="ok"}
        -- error is nil

    end

The next example shows an incorrect usage of ``splash:wait_for_resume()``:
the JavaScript code does not contain a ``main()`` function. ``result`` is
nil because ``splash.resume()`` is never called, and ``error`` contains
an error message explaining the mistake.

.. code-block:: lua

    function main(splash)

        local result, error = splash:wait_for_resume([[
            console.log('hello!');
        ]])

        -- result is nil
        -- error is "error: wait_for_resume(): no main() function defined"

    end

The next example shows error handling. If ``splash.error(…)`` is
called instead of ``splash.resume()``, then ``result`` will be ``nil``
and ``error`` will contain the string passed to ``splash.error(…)``.

.. code-block:: lua

    function main(splash)

        local result, error = splash:wait_for_resume([[
            function main(splash) {
                setTimeout(function () {
                    splash.error("Goodbye, cruel world!");
                }, 3000);
            }
        ]])

        -- result is nil
        -- error is "error: Goodbye, cruel world!"

    end

Your JavaScript code must either call ``splash.resume()`` or
``splash.error()`` exactly one time. Subsequent calls to either function
have no effect, as shown in the next example.

.. code-block:: lua

    function main(splash)

        local result, error = splash:wait_for_resume([[
            function main(splash) {
                setTimeout(function () {
                    splash.resume("ok");
                    splash.resume("still ok");
                    splash.error("not ok");
                }, 3000);
            }
        ]])

        -- result is {value="ok"}
        -- error is nil

    end

The next example shows the effect of the ``timeout`` argument. We have set
the ``timeout`` argument to 1 second, but our JavaScript code will not call
``splash.resume()`` for 3 seconds, which guarantees that
``splash:wait_for_resume()`` will time out.

When it times out, ``result`` will be nil, ``error`` will contain a string
explaining the timeout, and Lua will continue executing. Calling
``splash.resume()`` or ``splash.error()`` after a timeout has no effect.

.. code-block:: lua

    function main(splash)

        local result, error = splash:wait_for_resume([[
            function main(splash) {
                setTimeout(function () {
                    splash.resume("Hello, world!");
                }, 3000);
            }
        ]], 1)

        -- result is nil
        -- error is "error: One shot callback timed out while waiting for resume() or error()."

    end

.. note::

    The timeout must be >= 0. If the timeout is 0, then
    ``splash:wait_for_resume()`` will never timeout (although Splash's
    HTTP timeout still applies).

Note that your JavaScript code is not forceably canceled by a timeout: it may
continue to run until Splash shuts down the entire browser context.

See also: :ref:`splash-runjs`, :ref:`splash-jsfunc`, :ref:`splash-evaljs`.

.. _splash-autoload:

splash:autoload
---------------

Set JavaScript to load automatically on each page load.

**Signature:** ``ok, reason = splash:autoload{source_or_url, source=nil, url=nil}``

**Parameters:**

* source_or_url - either a string with JavaScript source code or an URL
  to load the JavaScript code from;
* source - a string with JavaScript source code;
* url - an URL to load JavaScript source code from.

**Returns:** ``ok, reason`` pair. If ``ok`` is nil, error happened and
``reason`` contains an error description.

**Async:** yes, but only when an URL of a remote resource is passed.

:ref:`splash-autoload` allows to execute JavaScript code at each page load.
:ref:`splash-autoload` doesn't doesn't execute the passed
JavaScript code itself. To execute some code once, *after* page is loaded
use :ref:`splash-runjs` or :ref:`splash-jsfunc`.

:ref:`splash-autoload` can be used to preload utility JavaScript libraries
or replace JavaScript objects before a webpage has a chance to do it.

Example:

.. code-block:: lua

    function main(splash)
        splash:autoload([[
            function get_document_title(){
               return document.title;
            }
        ]])
        assert(splash:go(splash.args.url))
        return splash:evaljs("get_document_title()")
    end

For the convenience, when a first :ref:`splash-autoload` argument starts
with "http://" or "https://" a script from the passed URL is loaded.
Example 2 - make sure a remote library is available:

.. code-block:: lua

    function main(splash)
        assert(splash:autoload("https://code.jquery.com/jquery-2.1.3.min.js"))
        assert(splash:go(splash.args.url))
        return splash:evaljs("$.fn.jquery")  -- return jQuery version
    end

To disable URL auto-detection use 'source' and 'url' arguments:

.. code-block:: lua

    splash:autoload{url="https://code.jquery.com/jquery-2.1.3.min.js"}
    splash:autoload{source="window.foo = 'bar';"}

It is a good practice not to rely on auto-detection when the argument
is not a constant.

If :ref:`splash-autoload` is called multiple times then all its scripts
are executed on page load, in order they were added.

See also: :ref:`splash-evaljs`, :ref:`splash-runjs`, :ref:`splash-jsfunc`,
:ref:`splash-wait-for-resume`.

.. _splash-http-get:

splash:http_get
---------------

Send an HTTP request and return a response without loading
the result to the browser window.

**Signature:** ``response = splash:http_get{url, headers=nil, follow_redirects=true}``

**Parameters:**

* url - URL to load;
* headers - a Lua table with HTTP headers to add/replace in the initial request;
* follow_redirects - whether to follow HTTP redirects.

**Returns:** a Lua table with the response in `HAR response`_ format.

**Async:** yes.

Example:

.. code-block:: lua

    local reply = splash:http_get("http://example.com")
    -- reply.content.text contains raw HTML data
    -- reply.status contains HTTP status code, as a number
    -- see HAR docs for more info

In addition to all HAR fields the response contains "ok" flag which is true
for successful responses and false when error happened:

.. code-block:: lua

    local reply = splash:http_get("some-bad-url")
    -- reply.ok == false

This method doesn't change the current page contents and URL.
To load a webpage to the browser use :ref:`splash-go`.

.. _HAR response: http://www.softwareishard.com/blog/har-12-spec/#response


.. _splash-set-content:

splash:set_content
------------------

Set the content of the current page and wait until the page loads.

**Signature:** ``ok, reason = splash:set_content{data, mime_type="text/html; charset=utf-8", baseurl=""}``

**Parameters:**

* data - new page content;
* mime_type - MIME type of the content;
* baseurl - external objects referenced in the content are located
  relative to baseurl.

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
page load; ``reason`` provides an information about error type.

**Async:** yes.

Example:

.. code-block:: lua

    function main(splash)
        assert(splash:set_content("<html><body><h1>hello</h1></body></html>"))
        return splash:png()
    end


.. _splash-html:

splash:html
-----------

Return a HTML snapshot of a current page (as a string).

**Signature:** ``html = splash:html()``

**Returns:** contents of a current page (as a string).

**Async:** no.

Example:

.. code-block:: lua

     -- A simplistic implementation of render.html endpoint
     function main(splash)
         splash:set_result_content_type("text/html; charset=utf-8")
         assert(splash:go(splash.args.url))
         return splash:html()
     end

Nothing prevents us from taking multiple HTML snapshots. For example, let's
visit first 10 pages on a website, and for each page store
initial HTML snapshot and an HTML snapshot after waiting 0.5s:

.. code-block:: lua

     -- Given an url, this function returns a table with
     -- two HTML snapshots: HTML right after page is loaded,
     -- and HTML after waiting 0.5s.
     function page_info(splash, url)
         local ok, msg = splash:go(url)
         if not ok then
             return {ok=false, reason=msg}
         end
         local res = {before=splash:html()}
         assert(splash:wait(0.5))  -- this shouldn't fail, so we wrap it in assert
         res.after = splash:html() -- the same as res["after"] = splash:html()
         res.ok = true
         return res
     end

     -- visit first 10 http://example.com/pages/<num> pages,
     -- return their html snapshots
     function main(splash)
         local result = {}
         for i=1,10 do
            local url = "http://example.com/pages/" .. page_num
            result[i] = page_info(splash, url)
         end
         return result
     end


.. _splash-png:

splash:png
----------

Return a `width x height` screenshot of a current page in PNG format.

**Signature:** ``png = splash:png{width=nil, height=nil, render_all=false, scale_method='raster'}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels;
* render_all - optional, if ``true`` render the whole webpage;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``

**Returns:** PNG screenshot data.

**Async:** no.

Without arguments ``splash:png()`` will take a snapshot of the current viewport.

*width* parameter sets the width of the resulting image.  If the viewport has a
different width, the image is scaled up or down to match the specified one.
For example, if the viewport is 1024px wide then ``splash:png{width=100}`` will
return a screenshot of the whole viewport, but the image will be downscaled to
100px width.

*height* parameter sets the height of the resulting image.  If the viewport has
a different height, the image is trimmed or extended vertically to match the
specified one without resizing the content.  The region created by such
extension is transparent.

To set the viewport size use :ref:`splash-set-viewport-size`,
:ref:`splash-set-viewport-full` or *render_all* argument.  ``render_all=true``
is equivalent to running ``splash:set_viewport_full()`` just before the
rendering and restoring the viewport size afterwards.

*scale_method* parameter must be either ``'raster'`` or ``'vector'``.  When
``scale_method='raster'``, the image is resized per-pixel.  When
``scale_method='vector'``, the image is resized per-element during rendering.
Vector scaling is more performant and produces sharper images, however it may
cause rendering artifacts, so use it with caution.

If the result of ``splash:png()`` is returned directly as a result of
"main" function, the screenshot is returned as binary data:

.. code-block:: lua

     -- A simplistic implementation of render.png endpoint
     function main(splash)
         splash:set_result_content_type("image/png")
         assert(splash:go(splash.args.url))
         return splash:png{
            width=splash.args.width,
            height=splash.args.height
         }
     end

If the result of ``splash:png()`` is returned as a table value, it is encoded
to base64 to make it possible to embed in JSON and build a data:uri
on a client (magic!):

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         return {png=splash:png()}
     end

If your script returns the result of ``splash:png()`` in a top-level
``"png"`` key (as we've done in a previous example) then Splash UI
will display it as an image.

.. _splash-jpeg:

splash:jpeg
-----------

Return a `width x height` screenshot of a current page in JPEG format.

**Signature:** ``jpeg = splash:jpeg{width=nil, height=nil, render_all=false, scale_method='raster', quality=75}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels;
* render_all - optional, if ``true`` render the whole webpage;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``
* quality - optional, quality of JPEG image, integer in range from ``0`` to ``100``

**Returns:** JPEG screenshot data.

**Async:** no.

Without arguments ``splash:jpeg()`` will take a snapshot of the current viewport.

*width* parameter sets the width of the resulting image.  If the viewport has a
different width, the image is scaled up or down to match the specified one.
For example, if the viewport is 1024px wide then ``splash:jpeg{width=100}`` will
return a screenshot of the whole viewport, but the image will be downscaled to
100px width.

*height* parameter sets the height of the resulting image.  If the viewport has
a different height, the image is trimmed or extended vertically to match the
specified one without resizing the content.  The region created by such
extension is white.

To set the viewport size use :ref:`splash-set-viewport-size`,
:ref:`splash-set-viewport-full` or *render_all* argument.  ``render_all=true``
is equivalent to running ``splash:set_viewport_full()`` just before the
rendering and restoring the viewport size afterwards.

*scale_method* parameter must be either ``'raster'`` or ``'vector'``.  When
``scale_method='raster'``, the image is resized per-pixel.  When
``scale_method='vector'``, the image is resized per-element during rendering.
Vector scaling is more performant and produces sharper images, however it may
cause rendering artifacts, so use it with caution.

*quality* parameter must be an integer in range from ``0`` to ``100``.
Values above ``95`` should be avoided; ``quality=100`` disables portions of
the JPEG compression algorithm, and results in large files with hardly any
gain in image quality.

If the result of ``splash:jpeg()`` is returned directly as a result of
"main" function, the screenshot is returned as binary data:

.. code-block:: lua

     -- A simplistic implementation of render.jpeg endpoint
     function main(splash)
         splash:set_result_content_type("image/jpeg")
         assert(splash:go(splash.args.url))
         return splash:jpeg{
            width=splash.args.width,
            height=splash.args.height
         }
     end

If the result of ``splash:jpeg()`` is returned as a table value, it is encoded
to base64 to make it possible to embed in JSON and build a data:uri
on a client (magic!):

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         return {jpeg=splash:jpeg()}
     end


.. _splash-har:

splash:har
----------

**Signature:** ``har = splash:har()``

**Returns:** information about pages loaded, events happened,
network requests sent and responses received in HAR_ format.

**Async:** no.

If your script returns the result of ``splash:har()`` in a top-level
``"har"`` key then Splash UI will give you a nice diagram with network
information (similar to "Network" tabs in Firefox or Chrome developer tools):

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         return {har=splash:har()}
     end

.. _HAR: http://www.softwareishard.com/blog/har-12-spec/


.. _splash-history:

splash:history
--------------

**Signature:** ``entries = splash:history()``

**Returns:** information about requests/responses for the pages loaded, in
`HAR entries`_ format.

**Async:** no.

``splash:history`` doesn't return information about related resources
like images, scripts, stylesheets or AJAX requests. If you need this
information use :ref:`splash-har`.

Let's get a JSON array with HTTP headers of the response we're displaying:

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         local entries = splash:history()
         -- #entries means "entries length"; arrays in Lua start from 1
         local last_entry = entries[#entries]
         return {
            headers = last_entry.response.headers
         }
     end

.. _HAR entries: http://www.softwareishard.com/blog/har-12-spec/#entries


.. _splash-url:

splash:url
----------

**Signature:** ``url = splash:url()``

**Returns:** the current URL.

**Async:** no.

.. _splash-get-cookies:

splash:get_cookies
------------------

**Signature:** ``cookies = splash:get_cookies()``

**Returns:** CookieJar contents - an array with all cookies available
for the script. The result is returned in `HAR cookies`_ format.

**Async:** no.

.. _HAR cookies: http://www.softwareishard.com/blog/har-12-spec/#cookies

Example result::

    [
        {
            "name": "TestCookie",
            "value": "Cookie Value",
            "path": "/",
            "domain": "www.example.com",
            "expires": "2016-07-24T19:20:30+02:00",
            "httpOnly": false,
            "secure": false,
        }
    ]


.. _splash-add-cookie:

splash:add_cookie
-----------------

Add a cookie.

**Signature:** ``cookies = splash:add_cookie{name, value, path=nil, domain=nil, expires=nil, httpOnly=nil, secure=nil}``

**Async:** no.

Example:

.. code-block:: lua

     function main(splash)
         splash:add_cookie{"sessionid", "237465ghgfsd", "/", domain="http://example.com"}
         splash:go("http://example.com/")
         return splash:html()
     end

.. _splash-init-cookies:

splash:init_cookies
-------------------

Replace all current cookies with the passed ``cookies``.

**Signature:** ``splash:init_cookies(cookies)``

**Parameters:**

* cookies - a Lua table with all cookies to set, in the same format as
  :ref:`splash-get-cookies` returns.

**Returns:** nil.

**Async:** no.

Example 1 - save and restore cookies:

.. code-block:: lua

     local cookies = splash:get_cookies()
     -- ... do something ...
     splash:init_cookies(cookies)  -- restore cookies

Example 2 - initialize cookies manually:

.. code-block:: lua

     splash:init_cookies({
         {name="baz", value="egg"},
         {name="spam", value="egg", domain="example.com"},
         {
             name="foo",
             value="bar",
             path="/",
             domain="localhost",
             expires="2016-07-24T19:20:30+02:00",
             secure=true,
             httpOnly=true,
         }
     })

     -- do something
     assert(splash:go("http://example.com"))


.. _splash-clear-cookies:

splash:clear_cookies
--------------------

Clear all cookies.

**Signature:** ``n_removed = splash:clear_cookies()``

**Returns:** a number of cookies deleted.

**Async:** no.

To delete only specific cookies
use :ref:`splash-delete-cookies`.

.. _splash-delete-cookies:

splash:delete_cookies
---------------------

Delete matching cookies.

**Signature:** ``n_removed = splash:delete_cookies{name=nil, url=nil}``

**Parameters:**

* name - a string, optional. All cookies with this name will be deleted.
* url - a string, optional. Only cookies that should be sent to this url
  will be deleted.

**Returns:** a number of cookies deleted.

**Async:** no.

This function does nothing when both *name* and *url* are nil.
To remove all cookies use :ref:`splash-clear-cookies` method.

.. _splash-lock-navigation:

splash:lock_navigation
----------------------

Lock navigation.

**Signature:** ``splash:lock_navigation()``

**Async:** no.

After calling this method the navigation away from the current page is no
longer permitted - the page is locked to the current URL.

.. _splash-unlock-navigation:

splash:unlock_navigation
------------------------

Unlock navigation.

**Signature:** ``splash:unlock_navigation()``

**Async:** no.

After calling this method the navigation away from the page becomes
permitted. Note that the pending navigation requests suppressed
by :ref:`splash-lock-navigation` won't be reissued.

.. _splash-set-result-content-type:

splash:set_result_content_type
------------------------------

Set Content-Type of a result returned to a client.

**Signature:** ``splash:set_result_content_type(content_type)``

**Parameters:**

* content_type - a string with Content-Type header value.

**Returns:** nil.

**Async:** no.

If a table is returned by "main" function then
``splash:set_result_content_type`` has no effect: Content-Type of the result
is set to ``application/json``.

This function **does not** set Content-Type header for requests
initiated by :ref:`splash-go`; this function is for setting Content-Type
header of a result.

Example:

.. code-block:: lua

     function main(splash)
         splash:set_result_content_type("text/xml")
         return [[
            <?xml version="1.0" encoding="UTF-8"?>
            <note>
                <to>Tove</to>
                <from>Jani</from>
                <heading>Reminder</heading>
                <body>Don't forget me this weekend!</body>
            </note>
         ]]
     end

See also: :ref:`splash-set-result-header` which allows to set any custom
response header, not only Content-Type.


.. _splash-set-result-header:

splash:set_result_header
------------------------

Set header of result response returned to splash client.

**Signature:** ``splash:set_result_header(name, value)``

**Parameters:**

* name of response header
* value of response header

**Returns:** nil.

**Async:** no.

This function **does not** set HTTP headers for responses
returned by :ref:`splash-go` or requests initiated by :ref:`splash-go`;
this function is for setting headers of splash response sent to client.

Example 1, set 'foo=bar' header:

.. code-block:: lua

     function main(splash)
         splash:set_result_header("foo", "bar")
         return "hello"
     end

Example 2, measure the time needed to build PNG screenshot and return it
result in an HTTP header:

.. code-block:: lua

     function main(splash)

         -- this function measures the time code takes to execute and returns
         -- it in an HTTP header
         function timeit(header_name, func)
             local start_time = splash:get_perf_stats().walltime
             local result = func()  -- it won't work for multiple returned values!
             local end_time = splash:get_perf_stats().walltime
             splash:set_result_header(header_name, tostring(end_time - start_time))
             return result
         end

         -- rendering script
         assert(splash:go(splash.args.url))
         local screenshot = timeit("X-Render-Time", function()
            return splash:png()
         end)
         splash:set_result_content_type("image/png")
         return screenshot
     end


.. _splash-images-enabled:

splash.images_enabled
---------------------

Enable/disable images.

**Signature:** ``splash.images_enabled = true/false``

By default, images are enabled. Disabling of the images can save a lot
of network traffic (usually around ~50%) and make rendering faster.
Note that this option can affect the JavaScript code inside page:
disabling of the images may change sizes and positions of DOM elements,
and scripts may read and use them.

Splash uses in-memory cache; cached images will be displayed
even when images are disabled. So if you load a page, then disable images,
then load a new page, then likely first page will display all images
and second page will display some images (the ones common with the first page).
Splash cache is shared between scripts executed in the same process, so you
can see some images even if they are disabled at the beginning of the script.

Example:

.. code-block:: lua

     function main(splash)
         splash.images_enabled = false
         assert(splash:go("http://example.com"))
         return {png=splash:png()}
     end

.. _splash-get-viewport-size:

splash:get_viewport_size
------------------------

Get the browser viewport size.

**Signature:** ``width, height = splash:get_viewport_size()``

**Returns:** two numbers: width and height of the viewport in pixels.

**Async:** no.


.. _splash-set-viewport-size:

splash:set_viewport_size
------------------------

Set the browser viewport size.

**Signature:** ``splash:set_viewport_size(width, height)``

**Parameters:**

* width - integer, requested viewport width in pixels;
* height - integer, requested viewport height in pixels.

**Returns:** nil.

**Async:** no.

This will change the size of the visible area and subsequent rendering
commands, e.g., :ref:`splash-png`, will produce an image with the specified
size.

:ref:`splash-png` uses the viewport size.

Example:

.. code-block:: lua

     function main(splash)
         splash:set_viewport_size(1980, 1020)
         assert(splash:go("http://example.com"))
         return {png=splash:png()}
     end

.. note::

   This will relayout all document elements and affect geometry variables, such
   as ``window.innerWidth`` and ``window.innerHeight``.  However
   ``window.onresize`` event callback will only be invoked during the next
   asynchronous operation and :ref:`splash-png` is notably synchronous, so if
   you have resized a page and want it to react accordingly before taking the
   screenshot, use :ref:`splash-wait`.

.. _splash-set-viewport-full:

splash:set_viewport_full
------------------------

Resize browser viewport to fit the whole page.

**Signature:** ``width, height = splash:set_viewport_full()``

**Returns:** two numbers: width and height the viewport is set to, in pixels.

**Async:** no.

``splash:set_viewport_full`` should be called only after page is loaded, and
some time passed after that (use :ref:`splash-wait`). This is an unfortunate
restriction, but it seems that this is the only way to make automatic resizing
work reliably.

See :ref:`splash-set-viewport-size` for a note about interaction with JS.

:ref:`splash-png` uses the viewport size.

Example:

.. code-block:: lua

     function main(splash)
         assert(splash:go("http://example.com"))
         assert(splash:wait(0.5))
         splash:set_viewport_full()
         return {png=splash:png()}
     end

.. _splash-set-user-agent:

splash:set_user_agent
---------------------

Overwrite the User-Agent header for all further requests.

**Signature:** ``splash:set_user_agent(value)``

**Parameters:**

* value - string, a value of User-Agent HTTP header.

**Returns:** nil.

**Async:** no.

.. _splash-set-custom-headers:

splash:set_custom_headers
-------------------------

Set custom HTTP headers to send with each request.

**Signature:** ``splash:set_custom_headers(headers)``

**Parameters:**

* headers - a Lua table with HTTP headers.

**Returns:** nil.

**Async:** no.

Headers are merged with WebKit default headers, overwriting WebKit values
in case of conflicts.

When ``headers`` argument of :ref:`splash-go` is used headers set with
``splash:set_custom_headers`` are not applied to the initial request:
values are not merged, ``headers`` argument of :ref:`splash-go` has
higher priority.

Example:

.. code-block:: lua

     splash:set_custom_headers({
        ["Header-1"] = "Value 1",
        ["Header-2"] = "Value 2",
     })

.. note::

    Named arguments are not supported for this function.

See also: :ref:`splash-on-request`.

.. _splash-get-perf-stats:

splash:get_perf_stats
---------------------

Return performance-related statistics.

**Signature:** ``stats = splash:get_perf_stats()``

**Returns:** a table that can be useful for performance analysis.

**Async:** no.

As of now, this table contains:

* ``walltime`` - (float) number of seconds since epoch, analog of ``os.clock``
* ``cputime`` - (float) number of cpu seconds consumed by splash process
* ``maxrss`` - (int) high water mark number of bytes of RAM consumed by splash
  process

.. _splash-on-request:

splash:on_request
-----------------

Register a function to be called before each HTTP request.

**Signature:** ``splash:on_request(callback)``

**Returns:** nil.

**Async:** no.

:ref:`splash-on-request` callback receives a single ``request`` argument.
``request`` contains the following fields:

* ``url`` - requested URL;
* ``method`` - HTTP method name in upper case, e.g. "GET";
* ``info`` - a table with request data in `HAR request`_ format
  (`url` and `method` values are duplicated here).

.. _HAR headers: http://www.softwareishard.com/blog/har-12-spec/#headers
.. _HAR request: http://www.softwareishard.com/blog/har-12-spec/#request
.. _HAR queryString: http://www.softwareishard.com/blog/har-12-spec/#queryString

These fields are for information only; changing them doesn't change
the request to be sent. To change or drop the request before sending use
one of the ``request`` methods:

* ``request:abort()`` - drop the request;
* ``request:set_url(url)`` - change request URL to a specified value;
* ``request:set_proxy{host, port, username=nil, password=nil, type='HTTP'}`` -
  set a proxy server to use for this request. Allowed proxy types are
  'HTTP' and 'SOCKS5'. Omit ``username`` and ``password`` arguments if a proxy
  doesn't need auth. When ``type`` is set to 'HTTP' HTTPS proxying should
  also work; it is implemented using CONNECT command.
* ``request:set_header(name, value)`` - set an HTTP header for this request.
  See also: :ref:`splash-set-custom-headers`.
* ``request:set_timeout(timeout)`` - set a timeout for this request,
  in seconds. If response is not fully received after the timeout,
  request is aborted.

A callback passed to :ref:`splash-on-request` can't call Splash
async methods like :ref:`splash-wait` or :ref:`splash-go`.

Example 1 - log all URLs requested:

.. code-block:: lua

    function main(splash)
        local urls = {}
        splash:on_request(function(request)
            urls[#urls+1] = request.url
        end)
        assert(splash:go(splash.args.url))
        return urls
    end

Example 2 - to log full request data use ``request.info`` attribute;
don't store ``request`` objects directly:

.. code-block:: lua

    function main(splash)
        local entries = {}
        splash:on_request(function(request)
            entries[#entries+1] = request.info
        end)
        assert(splash:go(splash.args.url))
        return entries
    end

Example 3 - drop all requests to resources containing ".css" in their URLs:

.. code-block:: lua

    splash:on_request(function(request)
        if string.find(request.url, ".css") ~= nil then
            request.abort()
        end
    end)

Example 4 - replace a resource:

.. code-block:: lua

    splash:on_request(function(request)
        if request.url == 'http://example.com/script.js' then
            request:set_url('http://mydomain.com/myscript.js')
        end
    end)

Example 5 - set a custom proxy server, with credentials passed in an HTTP
request to Splash:

.. code-block:: lua

    splash:on_request(function(request)
        request:set_proxy{
            host = "0.0.0.0",
            port = 8990,
            username = splash.args.username,
            password = splash.args.password,
        }
    end)

Example 6 - discard requests which take longer than 5 seconds to complete:

.. code-block:: lua

    splash:on_request(function(request)
        request:set_timeout(5.0)
    end)


.. note::

    `splash:on_request` method doesn't support named arguments.

.. _splash-on-response-headers:

splash:on_response_headers
--------------------------

Register a function to be called after response headers are received, before 
response body is read.

**Signature:** ``splash:on_response_headers(callback)``

**Returns:** nil.

**Async:** no.

:ref:`splash-on-response-headers` callback receives a single ``response`` argument.
``response`` contains following fields:

* ``url`` - requested URL;
* ``headers`` - HTTP headers of response
* ``info`` - a table with response data in `HAR response`_ format
* ``request`` - a table with request information 


These fields are for information only; changing them doesn't change
response received by splash. ``response`` has following methods:

* ``response:abort()`` - aborts reading of response body

A callback passed to :ref:`splash-on-response-headeers` can't call Splash
async methods like :ref:`splash-wait` or :ref:`splash-go`. ``response`` object
is deleted after exiting from callback, so you cannot use it outside callback.

``response.request`` available in callback contains following attributes:

* ``url`` - requested URL - can be different from response URL in case there is
  redirect
* ``headers`` - HTTP headers of request
* ``method`` HTTP method of request
* ``cookies`` - cookies in .har format

Example 1 - log content-type headers of all responses received while rendering

.. code-block:: lua

    function main(splash)
        local all_headers = {}
        splash:on_response_headers(function(response)
            local content_type = response.headers["Content-Type"]
            all_headers[response.url] = content_type
        end)
        assert(splash:go(splash.args.url))
        return all_headers
    end
    
Example 2 - abort reading body of all responses with content type ``text/css``

.. code-block:: lua

    function main(splash)
        splash:on_response_headers(function(response)
            local content_type = response.headers["Content-Type"]
            if content_type == "text/css" then
                response.abort()
            end
        end)
        assert(splash:go(splash.args.url))
        return splash:png()
    end

Example 3 - extract all cookies set by website without reading response body

.. code-block:: lua

    function main(splash)
        local cookies = ""
        splash:on_response_headers(function(response)
            local response_cookies = response.headers["Set-cookie"]
            cookies = cookies .. ";" .. response_cookies
            response.abort()
        end)
        assert(splash:go(splash.args.url))
        return cookies
    end

.. _splash-args:

splash.args
-----------

``splash.args`` is a table with incoming parameters. It contains
merged values from the orignal URL string (GET arguments) and
values sent using ``application/json`` POST request.

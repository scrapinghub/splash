.. _scripting-reference:

Splash Scripts Reference
========================

.. warning::

    Scripting support is an experimental feature for early adopters;
    API could change in future releases.

``splash`` object is passed to ``main`` function; via this object
a script can control the browser. Think of it as of an API to
a single browser tab.

Attributes
~~~~~~~~~~

.. _splash-args:

splash.args
-----------

``splash.args`` is a table with incoming parameters. It contains
merged values from the orignal URL string (GET arguments) and
values sent using ``application/json`` POST request.

.. _splash-js-enabled:

splash.js_enabled
-----------------

Enable or disable execution of JavaSript code embedded in the page.

**Signature:** ``splash.js_enabled = true/false``

JavaScript execution is enabled by default.

.. _splash-private-mode-enabled:

splash.private_mode_enabled
---------------------------

Enable or disable browser's private mode (incognito mode).

**Signature:** ``splash.private_mode_enabled = true/false``

Private mode is enabled by default unless you pass flag ``--disable-private-mode`` at Splash startup.
Note that if you disable private mode browsing data such as cookies or items kept in local
storage may persist between requests.

.. _splash-resource-timeout:

splash.resource_timeout
-----------------------

Set a default timeout for network requests, in seconds.

**Signature:** ``splash.resource_timeout = number``

Example - abort requests to remote resources if they take more than 10 seconds:

.. code-block:: lua

     function main(splash)
         splash.resource_timeout = 10.0
         assert(splash:go(splash.args.url))
         return splash:png()
     end

Zero or nil value means "no timeout".

Request timeouts set in :ref:`splash-on-request` using
``request:set_timeout`` have a priority over :ref:`splash-resource-timeout`.


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

.. literalinclude:: ../splash/examples/disable-images.lua
   :language: lua


.. _splash-plugins-enabled:

splash.plugins_enabled
----------------------

Enable or disable browser plugins (e.g. Flash).

**Signature:** ``splash.plugins_enabled = true/false``

Plugins are disabled by default.


.. _splash-response-body-enabled:

splash.response_body_enabled
----------------------------

Enable or disable response content tracking.

**Signature:** ``splash.response_body_enabled = true/false``

By default Splash doesn't keep bodies of each response in memory,
for efficiency reasons. It means that in :ref:`splash-on-response`
callbacks :ref:`splash-response-body` attribute is not available, and that
response content is not available in HAR_ exports. To make response content
available to a Lua script set ``splash.response_body_enabled = true``.

Note that :ref:`splash-response-body` is always available
in :ref:`splash-http-get` and :ref:`splash-http-post` results, regardless
of :ref:`splash-response-body-enabled` option.

To enable response content tracking per-request call
:ref:`splash-request-enable-response-body` in a :ref:`splash-on-request`
callback.

Methods
~~~~~~~

.. _splash-go:

splash:go
---------

Go to an URL. This is similar to entering an URL in a browser
address bar, pressing Enter and waiting until page loads.

**Signature:** ``ok, reason = splash:go{url, baseurl=nil, headers=nil, http_method="GET", body=nil, formdata=nil}``

**Parameters:**

* url - URL to load;
* baseurl - base URL to use, optional. When ``baseurl`` argument is passed
  the page is still loaded from ``url``, but it is rendered as if it was
  loaded from ``baseurl``: relative resource paths will be relative
  to ``baseurl``, and the browser will think ``baseurl`` is in address bar;
* headers - a Lua table with HTTP headers to add/replace in the initial request.
* http_method - optional, string with HTTP method to use when visiting url,
  defaults to GET, Splash also supports POST.
* body - optional, string with body for POST request
* formdata - Lua table that will be converted to urlencoded POST body and sent
  with header ``content-type: application/x-www-form-urlencoded``

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
page load; ``reason`` provides an information about error type.

**Async:** yes, unless the navigation is locked.

Five types of errors are reported (``ok`` can be ``nil`` in 5 cases):

1. There is a network error: a host doesn't exist, server dropped connection,
   etc. In this case ``reason`` is ``"network<code>"``. A list of possible
   error codes can be found in `Qt docs`_. For example, ``"network3"`` means
   a DNS error (invalid hostname).
2. Server returned a response with 4xx or 5xx HTTP status code.
   ``reason`` is ``"http<code>"`` in this case, i.e. for
   HTTP 404 Not Found ``reason`` is ``"http404"``.
3. Navigation is locked (see :ref:`splash-lock-navigation`); ``reason``
   is ``"navigation_locked"``.
4. Splash can't render the main page (e.g. because the first request was
   aborted) - ``reason`` is ``render_error``.
5. If Splash can't decide what caused the error, just ``"error"`` is returned.

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
links, ajax requests failed to load) use :ref:`splash-har`
or :ref:`splash-on-response`.

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
        while redirects_remaining > 0 do
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

.. literalinclude:: ../splash/examples/count-divs.lua
   :language: lua

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

==============  ==========================
Lua             JavaScript
==============  ==========================
string          string
number          number
boolean         boolean
table           Object or Array, see below
nil             undefined
==============  ==========================

Function result is converted from JavaScript to Lua data type. Only simple
JS objects are supported. For example, returning a function or a
JQuery selector from a wrapped function won't work.

By default Lua tables are converted to JavaScript Objects. To convert
a table to an Array use :ref:`treat-as-array`.

.. _js-lua-conversion-rules:

JavaScript → Lua conversion rules:

================  =================
JavaScript        Lua
================  =================
string            string
number            number
boolean           boolean
Object            table
Array             table, marked as array (see :ref:`treat-as-array`)
``undefined``     ``nil``
``null``          ``""`` (an empty string)
Date              string: date's ISO8601 representation, e.g.
                  ``1958-05-21T10:12:00.000Z``
function          ``nil``
circular object   ``nil``
host object       ``nil``
================  =================

.. note::

    The rule of thumb: if an argument or a return value can be serialized
    via JSON, then it is fine.

Note that currently you can't return DOM Elements, JQuery $ results and
similar structures from JavaScript to Lua; to pass data you have to
extract their attributes of interest as plain strings/numbers/objects/arrays:

.. code-block:: lua

    -- this function assumes jQuery is loaded in page
    local get_hrefs = splash:jsfunc([[
        function(sel){
            return $(sel).map(function(){return this.href}).get();
        }
    ]])
    local hrefs = get_hrefs("a.story-title")

Function arguments and return values are passed by value. For example,
if you modify an argument from inside a JavaScript function then the caller
Lua code won't see the changes, and if you return a global JS object and modify
it in Lua then object won't be changed in webpage context.

If a JavaScript function throws an error, it is re-throwed as a Lua error.
To handle errors it is better to use JavaScript try/catch because some of the
information about the error can be lost in JavaScript → Lua conversion.

See also: :ref:`splash-runjs`, :ref:`splash-evaljs`, :ref:`splash-wait-for-resume`,
:ref:`splash-autoload`, :ref:`treat-as-array`.

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
For example, the following innocent-looking code (using jQuery) will do
unnecessary work:

.. code-block:: lua

    splash:evaljs("$(console.log('foo'));")

A gotcha is that to allow chaining jQuery ``$`` function returns a huge object,
:ref:`splash-evaljs` tries to serialize it and convert to Lua,
which is a waste of resources. :ref:`splash-runjs` doesn't have this problem.

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

.. literalinclude:: ../splash/examples/preload-functions.lua
   :language: lua

For the convenience, when a first :ref:`splash-autoload` argument starts
with "http://" or "https://" a script from the passed URL is loaded.
Example 2 - make sure a remote library is available:

.. literalinclude:: ../splash/examples/preload-jquery.lua
   :language: lua


To disable URL auto-detection use 'source' and 'url' arguments:

.. code-block:: lua

    splash:autoload{url="https://code.jquery.com/jquery-2.1.3.min.js"}
    splash:autoload{source="window.foo = 'bar';"}

It is a good practice not to rely on auto-detection when the argument
is not a constant.

If :ref:`splash-autoload` is called multiple times then all its scripts
are executed on page load, in order they were added.

To revert Splash not to execute anything on page load use
:ref:`splash-autoload-reset`.

See also: :ref:`splash-evaljs`, :ref:`splash-runjs`, :ref:`splash-jsfunc`,
:ref:`splash-wait-for-resume`, :ref:`splash-autoload-reset`.


.. _splash-autoload-reset:

splash:autoload_reset
---------------------

Unregister all scripts previously set by :ref:`splash-autoload`.

**Signature:** ``splash:autoload_reset()``

**Returns:** nil

**Async:** no

After :ref:`splash-autoload-reset` call scripts set by :ref:`splash-autoload`
won't be loaded in future requests; one can use :ref:`splash-autoload` again
to setup a different set of scripts.

Already loaded scripts are not removed from the current page context.

See also: :ref:`splash-autoload`.


.. _splash-call-later:

splash:call_later
-----------------

Arrange for the callback to be called after the given delay seconds.

**Signature:** ``timer = splash:call_later(callback, delay)``

**Parameters:**

* callback - function to run;
* delay - delay, in seconds;

**Returns:** a handle which allows to cancel pending timer or reraise
exceptions happened in a callback.

**Async:** no.

Example 1 - take two HTML snapshots, at 1.5s and 2.5s after page
loading starts:

.. literalinclude:: ../splash/examples/call-later.lua
   :language: lua

:ref:`splash-call-later` returns a handle (a ``timer``). To cancel pending
task use its ``timer:cancel()`` method. If a callback is already
started ``timer:cancel()`` has no effect.

By default, exceptions raised in :ref:`splash-call-later` callback
stop the callback, but don't stop the main script. To reraise these errors
use ``timer:reraise()``.

:ref:`splash-call-later` arranges callback to be executed in future;
it never runs it immediately, even if delay is 0. When delay is 0
callback is executed no earlier than current function yields to event loop,
i.e. no earlier than some of the async functions is called.


.. _splash-http-get:

splash:http_get
---------------

Send an HTTP GET request and return a response without loading
the result to the browser window.

**Signature:** ``response = splash:http_get{url, headers=nil, follow_redirects=true}``

**Parameters:**

* url - URL to load;
* headers - a Lua table with HTTP headers to add/replace in the initial request;
* follow_redirects - whether to follow HTTP redirects.

**Returns:** a :ref:`splash-response`.

**Async:** yes.

Example:

.. code-block:: lua

    local reply = splash:http_get("http://example.com")

This method doesn't change the current page contents and URL.
To load a webpage to the browser use :ref:`splash-go`.

See also: :ref:`splash-http-post`, :ref:`splash-response`.


.. _splash-http-post:

splash:http_post
----------------

Send an HTTP POST request and return a response without loading
the result to the browser window.

**Signature:** ``response = splash:http_post{url, headers=nil, follow_redirects=true, body=nil}``

**Parameters:**

* url - URL to load;
* headers - a Lua table with HTTP headers to add/replace in the initial request;
* follow_redirects - whether to follow HTTP redirects.
* body - string with body of request, if you intend to send form submission,
  body should be urlencoded.

**Returns:** a :ref:`splash-response`.

**Async:** yes.

Example of form submission:

.. code-block:: lua

    local reply = splash:http_post{url="http://example.com", body="user=Frank&password=hunter2"}
    -- reply.body contains raw HTML data (as a binary object)
    -- reply.status contains HTTP status code, as a number
    -- see Response docs for more info

Example of JSON POST request:

.. code-block:: lua

    json = require("json")

    local reply = splash:http_post{
        url="http://example.com/post",
        body=json.encode({alpha="beta"}),
        headers={["content-type"]="application/json"}
    }


This method doesn't change the current page contents and URL.
To load a webpage to the browser use :ref:`splash-go`.

See also: :ref:`splash-http-get`, :ref:`lib-json`, :ref:`splash-response`.


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
visit first 3 pages on a website, and for each page store
initial HTML snapshot and an HTML snapshot after waiting 0.5s:

.. literalinclude:: ../splash/examples/multiple-pages.lua
   :language: lua

.. _splash-png:

splash:png
----------

Return a `width x height` screenshot of a current page in PNG format.

**Signature:** ``png = splash:png{width=nil, height=nil, render_all=false, scale_method='raster', region=nil}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels;
* render_all - optional, if ``true`` render the whole webpage;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``;
* region - optional, ``{left, top, right, bottom}`` coordinates of
  a cropping rectangle.

**Returns:** PNG screenshot data, as a :ref:`binary object <binary-objects>`.
When the result is empty ``nil`` is returned.

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

To render an arbitrary part of a page use *region* parameter. It should
be a table with ``{left, top, right, bottom}`` coordinates. Coordinates
are relative to current scroll position. Currently you can't take anything
which is not in a viewport; to make sure part of a page can be rendered call
:ref:`splash-set-viewport-full` before using :ref:`splash-png` with *region*.
This may be fixed in future Splash versions.

.. _example-render-element:

With ``region`` and a bit of JavaScript it is possible to render only a single
HTML element. Example:

.. literalinclude:: ../splash/examples/element-screenshot.lua
   :language: lua

*scale_method* parameter must be either ``'raster'`` or ``'vector'``.  When
``scale_method='raster'``, the image is resized per-pixel.  When
``scale_method='vector'``, the image is resized per-element during rendering.
Vector scaling is more performant and produces sharper images, however it may
cause rendering artifacts, so use it with caution.

The result of ``splash:png`` is a :ref:`binary object <binary-objects>`,
so you can return it directly from "main" function and it will be sent as
a binary image data with a proper Content-Type header:

.. literalinclude:: ../splash/examples/render-png.lua
   :language: lua

If the result of ``splash:png()`` is returned as a table value, it is encoded
to base64 to make it possible to embed in JSON and build a data:uri
on a client (magic!):

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         return {png=splash:png()}
     end

When an image is empty :ref:`splash-png` returns ``nil``. If you want Splash to
raise an error in these cases use ``assert``:

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         local png = assert(splash:png())
         return {png=png}
     end

See also: :ref:`splash-jpeg`, :ref:`binary-objects`,
:ref:`splash-set-viewport-size`, :ref:`splash-set-viewport-full`.


.. _splash-jpeg:

splash:jpeg
-----------

Return a `width x height` screenshot of a current page in JPEG format.

**Signature:** ``jpeg = splash:jpeg{width=nil, height=nil, render_all=false, scale_method='raster', quality=75, region=nil}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels;
* render_all - optional, if ``true`` render the whole webpage;
* scale_method - optional, method to use when resizing the image, ``'raster'``
  or ``'vector'``;
* quality - optional, quality of JPEG image, integer in range from ``0`` to ``100``;
* region - optional, ``{left, top, right, bottom}`` coordinates of
  a cropping rectangle.

**Returns:** JPEG screenshot data, as a :ref:`binary object <binary-objects>`.
When the image is empty ``nil`` is returned.

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

To render an arbitrary part of a page use *region* parameter. It should
be a table with ``{left, top, right, bottom}`` coordinates. Coordinates
are relative to current scroll position. Currently you can't take anything
which is not in a viewport; to make sure part of a page can be rendered call
:ref:`splash-set-viewport-full` before using :ref:`splash-jpeg` with *region*.
This may be fixed in future Splash versions.

With some JavaScript it is possible to render only a single HTML element
using ``region`` parameter. See an
:ref:`example <example-render-element>` in :ref:`splash-png` docs.

*scale_method* parameter must be either ``'raster'`` or ``'vector'``.  When
``scale_method='raster'``, the image is resized per-pixel.  When
``scale_method='vector'``, the image is resized per-element during rendering.
Vector scaling is more performant and produces sharper images, however it may
cause rendering artifacts, so use it with caution.

*quality* parameter must be an integer in range from ``0`` to ``100``.
Values above ``95`` should be avoided; ``quality=100`` disables portions of
the JPEG compression algorithm, and results in large files with hardly any
gain in image quality.

The result of ``splash:jpeg`` is a :ref:`binary object <binary-objects>`,
so you can return it directly from "main" function and it will be sent as
a binary image data with a proper Content-Type header:

.. code-block:: lua

     -- A simplistic implementation of render.jpeg endpoint
     function main(splash)
         assert(splash:go(splash.args.url))
         return splash:jpeg{
            width=splash.args.width,
            height=splash.args.height
         }
     end

If the result of ``splash:jpeg()`` is returned as a table value, it is encoded
to base64 to make it possible to embed in JSON and build a data:uri
on a client:

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         return {jpeg=splash:jpeg()}
     end

When an image is empty :ref:`splash-jpeg` returns ``nil``. If you want Splash to
raise an error in these cases use `assert`:

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         local jpeg = assert(splash:jpeg())
         return {jpeg=jpeg}
     end

See also: :ref:`splash-png`, :ref:`binary-objects`,
:ref:`splash-set-viewport-size`, :ref:`splash-set-viewport-full`.

Note that ``splash:jpeg()`` is often 1.5..2x faster than ``splash:png()``.

.. _splash-har:

splash:har
----------

**Signature:** ``har = splash:har{reset=false}``

**Parameters:**

* reset - optional; when ``true``, reset HAR records after taking a snapshot.

**Returns:** information about pages loaded, events happened,
network requests sent and responses received in HAR_ format.

**Async:** no.

Use :ref:`splash-har` to get information about network requests and
other Splash activity.

If your script returns the result of ``splash:har()`` in a top-level
``"har"`` key then Splash UI will give you a nice diagram with network
information (similar to "Network" tabs in Firefox or Chrome developer tools):

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         return {har=splash:har()}
     end

By default, when several requests are made (e.g. :ref:`splash-go` is called
multiple times), HAR data is accumulated and combined into a single object
(logs are still grouped by page).

If you want only updated information use ``reset`` parameter: it drops
all existing logs and start recording from scratch:

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url1))
         local har1 = splash:har{reset=true}
         assert(splash:go(splash.args.url2))
         local har2 = splash:har()
         return {har1=har1, har2=har2}
     end

By default, response content is not returned in HAR data. To enable it, use
:ref:`splash-response-body-enabled` option or
:ref:`splash-request-enable-response-body` method.

See also: :ref:`splash-har-reset`, :ref:`splash-on-response`,
:ref:`splash-response-body-enabled`, :ref:`splash-request-enable-response-body`.

.. _HAR: http://www.softwareishard.com/blog/har-12-spec/


.. _splash-har-reset:

splash:har_reset
----------------

**Signature:** ``splash:har_reset()``

**Returns:** nil.

**Async:** no.

Drops all internally stored HAR_ records. It is similar to
``splash:har{reset=true}``, but doesn't return anything.

See also: :ref:`splash-har`.

.. _splash-history:

splash:history
--------------

**Signature:** ``entries = splash:history()``

**Returns:** information about requests/responses for the pages loaded, in
`HAR entries`_ format.

**Async:** no.

``splash:history`` doesn't return information about related resources
like images, scripts, stylesheets or AJAX requests. If you need this
information use :ref:`splash-har` or :ref:`splash-on-response`.

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

See also: :ref:`splash-har`, :ref:`splash-on-response`.

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

.. _splash-set-result-status-code:

splash:set_result_status_code
-----------------------------

Set HTTP status code of a result returned to a client.

**Signature:** ``splash:set_result_status_code(code)``

**Parameters:**

* code - HTTP status code (a number 200 <= code <= 999).

**Returns:** nil.

**Async:** no.

Use this function to signal errors or other conditions to splash client
using HTTP status codes.

Example:

.. code-block:: lua

     function main(splash)
         local ok, reason = splash:go("http://www.example.com")
         if reason == "http500" then
             splash:set_result_status_code(503)
             splash:set_result_header("Retry-After", 10)
             return ''
         end
         return splash:png()
     end

Be careful with this function: some proxies can be configured to
process responses differently based on their status codes. See e.g. nginx
`proxy_next_upstream <http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_next_upstream>`_
option.

In case of unhandled Lua errors HTTP status code is set to 400 regardless
of the value set with :ref:`splash-set-result-status-code`.

See also: :ref:`splash-set-result-content-type`,
:ref:`splash-set-result-header`.


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

See also:

* :ref:`splash-set-result-header` which allows to set any custom
  response header, not only Content-Type.
* :ref:`binary-objects` which have their own method for setting result
  Content-Type.


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

See also: :ref:`splash-set-result-status-code`,
:ref:`splash-set-result-content-type`.


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

**Parameters:**

* callback - Lua function to call before each HTTP request.

**Returns:** nil.

**Async:** no.

:ref:`splash-on-request` callback receives a single ``request`` argument
(a :ref:`splash-request`).

To get information about a request use request
:ref:`attributes <splash-request-attributes>`;
to change or drop the request before sending use request
:ref:`methods <splash-request-methods>`;

A callback passed to :ref:`splash-on-request` can't call Splash
async methods like :ref:`splash-wait` or :ref:`splash-go`.

Example 1 - log all URLs requested using :ref:`splash-request-url` attribute:

.. literalinclude:: ../splash/examples/log-requests.lua
   :language: lua

Example 2 - to log full request information use :ref:`splash-request-info`
attribute; don't store ``request`` objects directly:

.. code-block:: lua

    treat = require("treat")
    function main(splash)
        local entries = treat.as_array({})
        splash:on_request(function(request)
            table.insert(entries, request.info)
        end)
        assert(splash:go(splash.args.url))
        return entries
    end

Example 3 - drop all requests to resources containing ".css" in their URLs
(see :ref:`splash-request-abort`):

.. code-block:: lua

    splash:on_request(function(request)
        if string.find(request.url, ".css") ~= nil then
            request.abort()
        end
    end)

Example 4 - replace a resource
(see :ref:`splash-request-set-url`):

.. code-block:: lua

    splash:on_request(function(request)
        if request.url == 'http://example.com/script.js' then
            request:set_url('http://mydomain.com/myscript.js')
        end
    end)

Example 5 - set a custom proxy server, with credentials passed in an HTTP
request to Splash (see :ref:`splash-request-set-proxy`):

.. code-block:: lua

    splash:on_request(function(request)
        request:set_proxy{
            host = "0.0.0.0",
            port = 8990,
            username = splash.args.username,
            password = splash.args.password,
        }
    end)

Example 6 - discard requests which take longer than 5 seconds to complete,
but allow up to 15 seconds for the first request
(see :ref:`splash-request-set-timeout`):

.. code-block:: lua

    local first = true
    splash.resource_timeout = 5
    splash:on_request(function(request)
        if first then
            request:set_timeout(15.0)
            first = false
        end
    end)

.. note::

    :ref:`splash-on-request` doesn't support named arguments.

See also: :ref:`splash-on-response`, :ref:`splash-on-response-headers`,
:ref:`splash-on-request-reset`, :ref:`lib-treat`, :ref:`splash-request`.

.. _splash-on-response-headers:

splash:on_response_headers
--------------------------

Register a function to be called after response headers are received, before
response body is read.

**Signature:** ``splash:on_response_headers(callback)``

**Parameters:**

* callback - Lua function to call for each response after
  response headers are received.

**Returns:** nil.

**Async:** no.

:ref:`splash-on-response-headers` callback receives a single ``response``
argument (a :ref:`splash-response`).

:ref:`splash-response-body` is not available in
a :ref:`splash-on-response-headers` callback because response body is not
read yet. That's the point of :ref:`splash-on-response-headers` method: you can
abort reading of the response body using :ref:`splash-response-abort` method.


.. XXX: should we allow to access response attributes (not methods)
   outside a callback?

A callback passed to :ref:`splash-on-response-headers` can't call Splash
async methods like :ref:`splash-wait` or :ref:`splash-go`. ``response`` object
is deleted after exiting from a callback, so you cannot use
it outside a callback.

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

.. literalinclude:: ../splash/examples/block-css.lua
   :language: lua

Example 3 - extract all cookies set by website without downloading
response bodies

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

.. note::

    :ref:`splash-on-response-headers` doesn't support named arguments.

See also: :ref:`splash-on-request`, :ref:`splash-on-response`,
:ref:`splash-on-response-headers-reset`, :ref:`splash-response`.

.. _splash-on-response:

splash:on_response
------------------

Register a function to be called after response is downloaded.

**Signature:** ``splash:on_response(callback)``

**Parameters:**

* callback - Lua function to call for each response after it is downloaded.

**Returns:** nil.

**Async:** no.

:ref:`splash-on-response` callback receives a single ``response`` argument
(a :ref:`splash-response`).

By default, this ``response`` object doesn't have :ref:`splash-response-body`
attribute. To enable it, use :ref:`splash-response-body-enabled` option
or :ref:`splash-request-enable-response-body` method.

.. note::

    :ref:`splash-on-response` doesn't support named arguments.

See also: :ref:`splash-on-request`, :ref:`splash-on-response-headers`,
:ref:`splash-on-response-reset`, :ref:`splash-response`,
:ref:`splash-response-body-enabled`, :ref:`splash-request-enable-response-body`.


.. _splash-on-request-reset:

splash:on_request_reset
-----------------------

Remove all callbacks registered by :ref:`splash-on-request`.

**Signature:** ``splash:on_request_reset()``

**Returns:** nil

**Async:** no.


.. _splash-on-response-headers-reset:

splash:on_response_headers_reset
--------------------------------

Remove all callbacks registered by :ref:`splash-on-response-headers`.

**Signature:** ``splash:on_response_headers_reset()``

**Returns:** nil

**Async:** no.


.. _splash-on-response-reset:

splash:on_response_reset
------------------------

Remove all callbacks registered by :ref:`splash-on-response`.

**Signature:** ``splash:on_response_reset()``

**Returns:** nil

**Async:** no.


.. _splash-get-version:

splash:get_version
------------------

Get Splash major and minor version.

**Signature:** ``version_info = splash:get_version()``

**Returns:** A table with version information.

**Async:** no.

As of now, this table contains:

* ``splash`` - (string) Splash version
* ``major`` - (int) Splash major version
* ``minor`` - (int) Splash minor version
* ``python`` - (string) Python version
* ``qt`` - (string) Qt version
* ``pyqt`` - (string) PyQt version
* ``webkit`` - (string) WebKit version
* ``sip`` - (string) SIP version
* ``twisted`` - (string) Twisted version

Example:

.. code-block:: lua

    function main(splash)
         local version = splash:get_version()
         if version.major < 2 and version.minor < 8 then
             error("Splash 1.8 or newer required")
         end
     end


.. _splash-mouse-click:

splash:mouse_click
------------------

Trigger mouse click event in web page.

**Signature:** ``splash:mouse_click(x, y)``

**Parameters:**

* x - number with x position of element to be clicked
  (distance from the left, relative to the current viewport)
* y - number with y position of element to be clicked
  (distance from the top, relative to the current viewport)

**Returns:** nil

**Async:** no.

Coordinates for mouse events must be relative to viewport.
Element on which action is performed must be inside viewport
(must be visible to the user). If element is outside viewport and
user needs to scroll to see it, you must either scroll to the element
with JavaScript or set viewport to full with
:ref:`splash-set-viewport-full`.

Mouse events are not propagated immediately, to see consequences of click
reflected in page source you must call :ref:`splash-wait`

If you want to get coordinates of html element use JavaScript
getClientRects_:

.. code-block:: lua

    -- Get button element dimensions with javascript and perform mouse click.
    function main(splash)
        assert(splash:go(splash.args.url))
        local get_dimensions = splash:jsfunc([[
            function () {
                var rect = document.getElementById('button').getClientRects()[0];
                return {"x": rect.left, "y": rect.top}
            }
        ]])
        splash:set_viewport_full()
        splash:wait(0.1)
        local dimensions = get_dimensions()
        splash:mouse_click(dimensions.x, dimensions.y)

        -- Wait split second to allow event to propagate.
        splash:wait(0.1)
        return splash:html()
    end

.. _getClientRects: https://developer.mozilla.org/en/docs/Web/API/Element/getClientRects

Under the hood :ref:`splash-mouse-click` performs :ref:`splash-mouse-press`
followed by :ref:`splash-mouse-release`.

At the moment only left click is supported.


.. _splash-mouse-hover:

splash:mouse_hover
------------------

Trigger mouse hover (JavaScript mouseover) event in web page.

**Signature:** ``splash:mouse_hover(x, y)``

**Parameters:**

* x - number with x position of element to be hovered on
  (distance from the left, relative to the current viewport)
* y - number with y position of element to be hovered on
  (distance from the top, relative to the current viewport)

**Returns:** nil

**Async:** no.

See notes about mouse events in :ref:`splash-mouse-click`.


.. _splash-mouse-press:

splash:mouse_press
------------------

Trigger mouse press event in web page.

**Signature:** ``splash:mouse_press(x, y)``

**Parameters:**

* x - number with x position of element over which mouse button is pressed
  (distance from the left, relative to the current viewport)
* y - number with y position of element over which mouse button is pressed
  (distance from the top, relative to the current viewport)

**Returns:** nil

**Async:** no.

See notes about mouse events in :ref:`splash-mouse-click`.


.. _splash-mouse-release:

splash:mouse_release
--------------------

Trigger mouse release event in web page.

**Signature:** ``splash:mouse_release(x, y)``

**Parameters:**

* x - number with x position of element over which mouse button is released
  (distance from the left, relative to the current viewport)
* y - number with y position of element over which mouse button is released
  (distance from the top, relative to the current viewport)

**Returns:** nil

**Async:** no.

See notes about mouse events in :ref:`splash-mouse-click`.


.. _splash-with-timeout:

splash:with_timeout
-------------------

Run the function with the allowed timeout

**Signature:** ``ok, result = splash:with_timeout(func, timeout)``

**Parameters:**

* func - the function to run
* timeout - timeout, in seconds

**Returns:** ``ok, result`` pair. If ``ok`` is not ``true`` then error happened during
the function call or the timeout expired; ``result`` provides an information
about error type. If ``result`` is equal to ``timeout_over`` then the specified timeout period elapsed.
Otherwise, if ``ok`` is ``true`` then ``result`` contains the result of the executed function.
If your function returns several values, they will be assigned to the next variables to ``result``.

**Async:** yes.

Example 1:

.. literalinclude:: ../splash/examples/with-timeout.lua
   :language: lua

Example 2 - the function returns several values

.. code-block:: lua

    function main(splash)
        local ok, result1, result2, result3 = splash:with_timeout(function()
            splash:wait(0.5)
            return 1, 2, 3
        end, 1)

        return result1, result2, result3
    end

Note that if the specified timeout period elapsed Splash will try to interrupt the running function.
However, Splash scripts are executed in `cooperative multitasking`_ manner and because of that sometimes
Splash won't be able to stop your running function upon timeout expiration. In two words, cooperative multitasking
means that the managing program (in our example, it is Splash scripting engine) won't stop the running function if it doesn't
*ask* for that. In Splash scripting the running function can be interrupted only if some *async* operation was called.
On the contrary, non of the *sync* operations can be interrupted.

.. note::

    Splash scripts are executing in `cooperative multitasking`_ manner. You should be careful while running sync
    functions.

Let's see the difference in examples.

Example 3:

.. code-block:: lua

    function main(splash)
        local ok, result = splash:with_timeout(function()
            splash:go(splash.args.url) -- during this operation the current function can be stopped
            splash:evaljs(long_js_operation) -- during JS function evaluation the function cannot be stopped
            local png = splash:png() -- sync operation and during it the function cannot be stopped
            return png
        end, 0.1)

        return result
    end
.. _cooperative multitasking: https://en.wikipedia.org/wiki/Cooperative_multitasking


.. _splash-send-keys:

splash:send_keys
----------------

Send keyboard events to page context.

**Signature:** ``splash:send_keys(keys)``

**Parameters**

* keys - string representing the keys to be sent as keyboard events.

**Returns:** nil

**Async:** no.

Key sequences are specified by using a small subset of emacs edmacro syntax:

* whitespace is ignored and only used to separate the different keys
* characters are literally represented
* words within brackets represent function keys, like ``<Return>``, ``<Left>``
  or ``<Home>``. See `Qt docs`__ for a full list of function keys. ``<Foo>``
  will try to match ``Qt::Key_Foo``.

__ http://doc.qt.io/qt-5/qt.html#Key-enum

Following table shows some examples of macros and what they would generate on
an input:

============================    ===============
Macro                           Result
============================    ===============
``Hello World``                 ``HelloWorld``
``Hello <Space> World``         ``Hello World``
``< S p a c e >``               ``<Space>``
``Hello <Home> <Delete>``       ``ello``
``Hello <Backspace>``           ``Hell``
============================    ===============

Key events are not propagated immediately until event loop regains control,
thus :ref:`splash-wait` must be called to reflect the events.

.. _Qt key-enum: http://doc.qt.io/qt-5/qt.html#Key-enum

.. _splash-send-text:


splash:send_text
----------------

Send text as input to page context, literally, character by character.

**Signature:** ``splash:send_text(text)``

**Parameters:**

* text - string to be sent as input.

**Returns:** nil

**Async:** no.

Key events are not propagated immediately until event loop regains control,
thus :ref:`splash-wait` must be called to reflect the events.


This function in conjuction with :ref:`splash-send-keys` covers most needs on
keyboard input, such as filling in forms and submitting them.

Example 1: focus first input, fill in a form and submit

.. code-block:: lua

    function main(splash)
        assert(splash:go(splash.args.url))
        assert(splash:wait(0.5))
        splash:send_keys("<Tab>")
        splash:send_text("zero cool")
        splash:send_keys("<Tab>")
        splash:send_text("hunter2")
        splash:send_keys("<Return>")
        -- note how this could be translated to
        -- splash:send_keys("<Tab> zero <Space> cool <Tab> hunter2 <Return>")
        assert(splash:wait(0))
        -- ...
    end

Example 2: focus inputs with javascript or :ref:`splash-mouse-click`

We can't always assume that a `<Tab>` will focus the input we want or an
`<Enter>` will submit a form. Selecting an input can either be accomplished
by focusing it or by clicking it. Submitting a form can also be done by
firing a submit event on the form, or simply by clicking on the submit button.

The following example will focus an input, fill in a form and click on the
submit button using :ref:`splash-mouse-click`. It assumes there are two
arguments passed to splash, `username` and `password`.

.. code-block:: lua

    function main(splash)
        local get_elem_pos = splash:jsfunc([[
            function (selector) {
                var elem = document.querySelector(selector);
                var rect = elem.getClientRects()[0];
                return {"x": rect.left, "y": rect.top}
            }
        ]])

        local focus = splash:jsfunc([[
            function (selector) {
                var elem = document.querySelector(selector);
                return elem.focus();
            }
        ]])

        assert(splash:go(splash.args.url))
        assert(splash:wait(0.5))
        focus('input[name=username]')
        splash:send_text(splash.args.username)
        assert(splash:wait(0))
        focus('input[name=password]')
        splash:send_text(splash.args.password)
        local submit = get_elem_pos('input[type=submit]')
        splash:mouse_click(submit.x, submit.y)
        assert(splash:wait(0))
        -- Usually, wait for the submit request to finish
        -- ...
    end

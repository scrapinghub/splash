.. _scripts:

Splash Scripts Tutorial
=======================

Intro
-----

Splash can execute custom rendering scripts written in Lua_ programming language.
This allows to use Splash as a browser automation tool similar to PhantomJS_.
To execute a script and get the result back send it to :ref:`render.lua`
endpoint in a :ref:`lua_source <arg-lua-source>` argument.

.. note::

    Most likely you'll be able to follow Splash scripting examples even
    without knowing Lua. Nevertheless, the language worths learning - it
    is easy to get started and there are good online resources available,
    e.g. the `Programming in Lua`_ book.

.. _Programming in Lua: http://www.lua.org/pil/contents.html
.. _Lua: http://www.lua.org/
.. _PhantomJS: http://phantomjs.org/

Let's start with a basic example:

.. code-block:: lua

     function main(splash)
         splash:go("http://example.com")
         splash:wait(0.5)
         local title = splash:runjs("document.title")
         return {title=title}
     end

If we submit this script to :ref:`render.lua` endpoint in a ``lua_source``
argument, Splash will go to example.com website, wait until it loads,
then wait 0.5s more, then get page title (by evaluating a JavaScript snippet
in page context), and then return the result as a JSON encoded object.

.. note::

    Splash UI provides an easy way to try scripts: it provides a code editor
    for Lua and a button to submit a script to ``render.lua``. Visit
    http://127.0.0.1:8050/ (or whatever host/port Splash is listening to).

Entry Point: the "main" Function
--------------------------------

The script must provide "main" function; this function is called by Splash.
The result of this function is returned as an HTTP response.
Script could contain other helper functions and statements,
but 'main' is required.

In the first example 'main' function returned a Lua table (an associative array
similar to JavaScript Object or Python dict). Such results are returned as
JSON. This will return ``{"hello":"world!"}`` string as an HTTP response:

.. code-block:: lua

    function main(splash)
        return {hello="world!"}
    end

Script can also return a string:

.. code-block:: lua

    function main(splash)
        return 'hello'
    end

Strings are returned as-is (unlike tables they are not encoded to JSON).
Let's check it with curl::

    $ curl 'http://127.0.0.1:8050/render.lua?lua_source=function+main%28splash%29%0D%0A++return+%27hello%27%0D%0Aend'
    hello

API Overview
------------

* :ref:`splash:go() <splash-go>` is a method to load an URL in the "browser tab";
* :ref:`splash:wait() <splash-wait>` allows to pause script execution to give
  a webpage some time to live on its own;
* :ref:`splash:runjs() <splash-runjs>` allows to execute JavaScript code in page
  context and get results back;
* :ref:`splash:html() <splash-html>` returns a HTML snapshot of the current page;
* :ref:`splash:png() <splash-png>` creates a screenshot of the webpage in PNG format;
* :ref:`splash:har() <splash-har>` returns information about pages loaded,
  events happened, network requests sent and responses received in HAR_ format;
* :ref:`splash:set_result_content_type() <splash-set-result-content-type>`
  to control how to return the result;
* :ref:`splash.args <splash-args>` provides a table with incoming HTTP arguments;


.. _HAR: http://www.softwareishard.com/blog/har-12-spec/

Where Are My Callbacks?
-----------------------

Here is a part of the first example:

.. code-block:: lua

    splash:go("http://example.com")
    splash:wait(0.5)
    local title = splash:runjs("document.title")

The code looks like a standard procedural code; there are no callbacks
or fancy control flow structures. It doesn't mean Splash works in a synchronous
way; under the hood it is still async. When you call ``splash.wait(0.5)``,
Splash switches from the script to other tasks, and comes back after 0.5s.

It is possible to use loops, conditional statements, functions as usual
in Splash scripts; this enables a more straightforward code.

Let's check an `example <https://github.com/ariya/phantomjs/blob/master/examples/follow.js>`__
PhantomJS script:

.. code-block:: javascript

    var users = ["PhantomJS", "ariyahidayat", /*...*/];

    function follow(user, callback) {
        var page = require('webpage').create();
        page.open('http://mobile.twitter.com/' + user, function (status) {
            if (status === 'fail') {
                console.log(user + ': ?');
            } else {
                var data = page.evaluate(function () {
                    return document.querySelector('div.profile td.stat.stat-last div.statnum').innerText;
                });
                console.log(user + ': ' + data);
            }
            page.close();
            callback.apply();
        });
    }
    function process() {
        if (users.length > 0) {
            var user = users[0];
            users.splice(0, 1);
            follow(user, process);
        } else {
            phantom.exit();
        }
    }
    process();

The code is arguably tricky: ``process`` function implements a loop
by creating a chain of callbacks; ``follow`` function doesn't return a value
(it would be more complex to handle), instead of that the result is logged
to console.

A similar Splash script:

.. code-block:: lua

    users = {'PhantomJS', 'ariyahidayat'}

    function follow(splash, user)
        local ok, msg = splash:go('http://mobile.twitter.com/' .. user)
        if not ok then
            return "?"
        end
        return splash:runjs([[
            document.querySelector('div.profile td.stat.stat-last div.statnum').innerText;
        ]]);
    end

    function process(splash, users)
        local result = {}
        for idx, user in ipairs(users) do
            result[user] = follow(splash, user)
        end
        return result
    end

    function main(splash)
        local users = process(splash, users)
        return {users=users}
    end

Some observations:

* ``follow`` function can just return a result; also, it doesn't need
  a "callback" argument;
* instead of a ``page.open`` callback which receives "status" argument
  there is a "blocking" ``splash:go`` call which returns "ok" flag;
* ``process`` function can use a standard Lua ``for`` loop;
* it is clear where is an entry point and where processing stops;
* instead of console messages we've got a JSON HTTP API;
* apparently, PhantomJS allows to create multiple ``page`` objects and
  run several ``page.open`` requests in parallel (?); Splash only provides
  a single "browser tab" to a script via its ``splash`` parameter of ``main``
  function (but you're free to send multiple concurrent requests with
  Lua scripts to Splash).
* contrary to what was said earlier, some Lua knowledge is helpful, e.g.
  ``ipairs``, ``[[multi-line strings]]`` or string concatenation
  via ``..`` could be unfamiliar.


There are PhantomJS wrappers like CasperJS_ and NightmareJS_ which bring
a sync-looking syntax to PhantomJS scripts by providing custom control flow
mini-languages, but they all have their own gotchas and edge cases
(loops? moving code to helper functions? error handling?). Splash scripts are
standard Lua code.

.. _CasperJS: http://casperjs.org/
.. _NightmareJS:

.. note::

    For the curious, the implementation uses Lua coroutines.

    In Splash scripts it is not explicit which calls are async and which calls
    are blocking. It is a common criticism of coroutines/greenlets; check e.g.
    `this <https://glyph.twistedmatrix.com/2014/02/unyielding.html>`__ article
    for a description of the problem. However, we feel that in Splash scripts
    negative effects are not quite there: scripts are meant to be small,
    shared state is minimized, and an API is designed to execute a single
    command at time, so in most cases the control flow is linear.

    If you want to be safe then think of all ``splash`` methods as of async;
    consider that after you call ``splash:foo()`` a webpage being
    rendered can change. Often that's the point of calling a method,
    e.g. ``splash:wait(time_ms)`` or ``splash:go(url)`` only make sense because
    webpage changes after calling them, but still - keep it in mind.


.. _splash-object:

Splash Scripts Reference
========================

A ``Splash`` instance is passed to ``main`` function; via this object
a script can control the browser.

.. _splash-go:

splash:go
---------

Go to url. This is similar to entering an URL in a browser
address tab, pressing Enter and waiting until page loads.

**Signature:** ``ok, msg = splash.go(url, baseurl=nil)``

**Parameters:**

* url - URL to load;
* baseurl - base URL to use;

**Returns:** ``ok, msg`` pair. If ``ok`` is nil then error happened during
page load, and ``msg`` contains a description of the error.

Example:

.. code-block:: lua

    local ok, msg = splash:go("http://example.com")
    if not ok:
        -- handle errors
    end
    -- page is loaded


Lua "assert" can be used as a shortcut for error handling:

.. code-block:: lua

    assert(splash:go("http://example.com"))
    -- page is loaded

.. _splash-wait:

splash:wait
-----------

Wait for ``time`` seconds, then return ``true``.

**Signature:** ``ok, reason = splash:wait(time, cancel_on_redirect=false, cancel_on_error=true)``

**Parameters:**

* time - time to wait, in seconds;
* cancel_on_redirect - if true (not a default) and a redirect
  happened while waiting (for example, it could be initiated by JS code),
  then ``splash:wait`` stops earlier and returns ``nil, "redirect"``.
* cancel_on_error - if true (default) and an error which prevents page
  from being rendered happened while waiting (e.g. an internal WebKit error
  or a network error like a redirect to a non-resolvable host)
  then ``splash:wait`` stops earlier and returns ``nil, "error"``.

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then the timer was stopped
prematurely, and ``reason`` contains a string with a reason
(possible values are "error" and "redirect").

Example:

.. code-block:: lua

     -- go to example.com, wait 0.5s, return rendered html, ignore all errors.
     function main(splash)
         splash:go("http://example.com")
         splash:wait(0.5)
         return {html=splash:html()}
     end

Example of a function that waits for a given time, restarting a wait
timer after each redirect:

.. code-block:: lua

    function wait_restarting_on_redirects(splash, time, max_redirects)
        local redirects_remaining = max_redirects
        while redirects_remaining do
            local ok, reason = self:wait(time)
            if reason ~= 'redirect' then
                return ok, reason
            end
            redirects_remaining = redirects_remaining - 1
        end
        error("Too many redirects")
    end


.. _splash-runjs:

splash:runjs
------------

Execute JavaScript in page context and return the result of the last statement.

**Signature:** ``result = splash:runjs(source)``

**Parameters:**

* source - a string with JavaScript source code to execute.

**Returns:** the result of the last statement in `source`,
serialized from JavaScript to Lua. JavaScript strings, numbers, booleans,
Objects, Date and RegExp instances are supported. ``undefined`` is returned
as Lua ``nil``; ``null`` is converted to an empty string. Arrays are not
currently supported (use Objects instead).

Example:

.. code-block:: lua

    local title = splash:runjs("document.title")


.. _splash-html:

splash:html
-----------

Return a HTML snapshot of a current page (as a string).

**Signature:** ``html = splash:html()``

**Returns:** contents of a current page (as a string).

Example:

.. code-block:: lua

     --
     -- A simplistic implementation of render.html endpoint
     --
     function main(splash)
         splash:set_result_content_type("text/html; charset=utf-8")
         assert(splash:go(splash.args.url))
         return splash:html()
     end

.. _splash-png:

splash:png
----------

Return a `width x height` screenshot of a current page in PNG format.

**Signature:** ``png = splash:png(width=nil, height=nil)``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels.

**Returns:** PNG screenshot data.

TODO: document what default values mean

*width* and *height* arguments set a size of the resulting image,
not a size of an area screenshot is taken of. For example, if the viewport
has a width of 1024px wide then ``splash:png{width=100}`` will return a
screenshot of a whole viewport, but an image will be downscaled to 100px width.

If the result of ``splash:png()`` returned directly as a result of
"main" function, the screenshot is returned as binary data:

.. code-block:: lua

     --
     -- A simplistic implementation of render.png endpoint
     --
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
on a client:

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         return {png=splash:png()}
     end

.. _splash-har:

splash:har
----------

**Signature:** ``har = splash:har()``

**Returns:** information about pages loaded, events happened,
network requests sent and responses received in HAR_ format.

If your script returns the result of ``splash:har()`` in a top-level
``"har"`` key then Splash UI will give you a nice diagram with network
information (similar to "Network" tabs in Firefox or Chrome developer tools):

.. code-block:: lua

     function main(splash)
         assert(splash:go(splash.args.url))
         return {har=splash:har()}
     end


.. _splash-set-result-content-type:

splash:set_result_content_type
------------------------------

Set Content-Type of a result returned to a client.

**Signature:** ``splash:set_result_content_type(content_type)``

**Parameters:**

* content_type - a string with Content-Type header value.

If a table is returned by "main" function then
``splash:set_result_content_type`` has no effect: Content-Type of the result
is set to ``application/json``.

This function **does not** set Content-Type header for requests
initiated by :ref:`splash-go`; this function is for setting Content-Type
header of a result.

.. _splash-args:

splash.args
-----------

``splash.args`` is a table with incoming parameters. It contains
merged values from the orignal URL string (GET arguments) and
values sent using ``application/json`` POST request.

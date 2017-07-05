.. _scripting-tutorial:

Splash Scripts Tutorial
=======================

Intro
-----

Splash can execute custom rendering scripts written in the Lua_
programming language. This allows us to use Splash as a browser automation
tool similar to PhantomJS_.

To execute a script and get the result back send it to the :ref:`execute`
(or :ref:`run`) endpoint in a :ref:`lua_source <arg-lua-source>` argument.
We'll be using :ref:`execute` endpoint in this tutorial.

.. note::

    Most likely you'll be able to follow Splash scripting examples even
    without knowing Lua; nevertheless, the language is worth learning.
    With Lua you can, for example, write Redis_, Nginx_, Apache_,
    `World of Warcraft`_ scripts, create mobile apps using
    `Corona`_ or use the state of the art Deep Learning
    framework Torch7_. It is easy to get started and there are good online
    resources available like the tutorial `Learn Lua in 15 minutes`_ and the
    book `Programming in Lua`_.

.. _Learn Lua in 15 minutes: http://tylerneylon.com/a/learn-lua/
.. _Nginx: https://github.com/openresty/lua-nginx-module
.. _Redis: http://redis.io/commands/EVAL
.. _Apache: http://httpd.apache.org/docs/trunk/mod/mod_lua.html
.. _World of Warcraft: http://www.wowwiki.com/Lua
.. _Corona: https://coronalabs.com/
.. _Torch7: http://torch.ch/
.. _Programming in Lua: http://www.lua.org/pil/contents.html
.. _Lua: http://www.lua.org/
.. _PhantomJS: http://phantomjs.org/

Let's start with a basic example:

.. literalinclude:: ../splash/examples/return-title.lua
   :language: lua

If we submit this script to the :ref:`execute` endpoint in a ``lua_source``
argument, Splash will go to the example.com website, wait until it loads,
wait another half-second, then get the page title (by evaluating a JavaScript
snippet in page context), and then return the result as a JSON encoded object.

.. note::

    Splash UI provides an easy way to try scripts: there is a code editor
    for Lua and a button to submit a script to ``execute``. Visit
    http://127.0.0.1:8050/ (or whatever host/port Splash is listening to).

    To run scripts from your programming environment you need to figure
    out how to send HTTP requests. Check :ref:`using-http-api` FAQ
    section - it contains recipes for some of the common setupts
    (e.g. Python + requests library).


Entry Point: the "main" Function
--------------------------------

The script must provide a "main" function which is called by Splash. The
result is returned as an HTTP response. The script could contain other
helper functions and statements, but 'main' is required.

In the first example 'main' function returned a Lua table (an associative array
similar to JavaScript Object or Python dict). Such results are returned as
JSON.

The following will return the string ``{"hello":"world!"}`` as an HTTP response:

.. code-block:: lua

    function main(splash)
        return {hello="world!"}
    end

The script can also return a string:

.. code-block:: lua

    function main(splash)
        return 'hello'
    end

Strings are returned as-is (unlike tables they are not encoded to JSON).
Let's check it with curl::

    $ curl 'http://127.0.0.1:8050/execute?lua_source=function+main%28splash%29%0D%0A++return+%27hello%27%0D%0Aend'
    hello

The "main" function receives an object that allows us to control the "browser
tab". All Splash features are exposed using this object. By convention, this
argument is called "splash", but you are not required to follow this convention:

.. code-block:: lua

    function main(please)
        please:go("http://example.com")
        please:wait(0.5)
        return "ok"
    end

Where Are My Callbacks?
-----------------------

Here is a snippet from our first example:

.. code-block:: lua

    splash:go("http://example.com")
    splash:wait(0.5)
    local title = splash:evaljs("document.title")

The code looks like standard procedural code; there are no callbacks or fancy
control-flow structures. It doesn't mean Splash works in a synchronous
way; under the hood it is still async. When you call ``splash.wait(0.5)``,
Splash switches from the script to other tasks, and comes back after 0.5s.

It is possible to use loops, conditional statements, functions as usual
in Splash scripts which enables more straightforward coding.

Let's check an `example <https://github.com/ariya/phantomjs/blob/master/examples/render_multi_url.js>`__
PhantomJS script:

.. code-block:: javascript

    // Render Multiple URLs to file

    "use strict";
    var RenderUrlsToFile, arrayOfUrls, system;

    system = require("system");

    /*
    Render given urls
    @param array of URLs to render
    @param callbackPerUrl Function called after finishing each URL, including the last URL
    @param callbackFinal Function called after finishing everything
    */
    RenderUrlsToFile = function(urls, callbackPerUrl, callbackFinal) {
        var getFilename, next, page, retrieve, urlIndex, webpage;
        urlIndex = 0;
        webpage = require("webpage");
        page = null;
        getFilename = function() {
            return "rendermulti-" + urlIndex + ".png";
        };
        next = function(status, url, file) {
            page.close();
            callbackPerUrl(status, url, file);
            return retrieve();
        };
        retrieve = function() {
            var url;
            if (urls.length > 0) {
                url = urls.shift();
                urlIndex++;
                page = webpage.create();
                page.viewportSize = {
                    width: 800,
                    height: 600
                };
                page.settings.userAgent = "Phantom.js bot";
                return page.open("http://" + url, function(status) {
                    var file;
                    file = getFilename();
                    if (status === "success") {
                        return window.setTimeout((function() {
                            page.render(file);
                            return next(status, url, file);
                        }), 200);
                    } else {
                        return next(status, url, file);
                    }
                });
            } else {
                return callbackFinal();
            }
        };
        return retrieve();
    };

    arrayOfUrls = null;

    if (system.args.length > 1) {
        arrayOfUrls = Array.prototype.slice.call(system.args, 1);
    } else {
        console.log("Usage: phantomjs render_multi_url.js [domain.name1, domain.name2, ...]");
        arrayOfUrls = ["www.google.com", "www.bbc.co.uk", "phantomjs.org"];
    }

    RenderUrlsToFile(arrayOfUrls, (function(status, url, file) {
        if (status !== "success") {
            return console.log("Unable to render '" + url + "'");
        } else {
            return console.log("Rendered '" + url + "' at '" + file + "'");
        }
    }), function() {
        return phantom.exit();
    });

The code is (arguably) tricky: ``RenderUrlsToFile`` function implements a loop
by creating a chain of callbacks; ``page.open`` callback doesn't return a value
(it would be more complex to implement) - the result is saved on disk.

A similar Splash script:

.. literalinclude:: ../splash/examples/render-multiple.lua
   :language: lua

It is not doing exactly the same work - instead of saving screenshots
to files we're returning PNG data to the client via HTTP API.

Observations:

* instead of a ``page.open`` callback which receives "status" argument
  there is a "blocking" :ref:`splash-go` call which returns "ok" flag;
* we're using a standard Lua ``for`` loop without a need to create
  a recursive callback chain;
* some Lua knowledge is helpful to be productive in Splash Scripts:
  ``ipairs`` or string concatenation via ``..`` could be unfamiliar;
* error handling is different: in case of an HTTP 4xx or 5xx error
  PhantomJS doesn't return an error code to ``page.open`` callback - example
  script will get a screenshot nevertheless because "status" won't
  be "fail"; in Splash this error will be detected;
* instead of console messages and local files we've created a JSON HTTP API;
* apparently, PhantomJS allows to create multiple ``page`` objects and
  run several ``page.open`` requests in parallel (?); Splash only provides
  a single "browser tab" to a script via its ``splash`` parameter of ``main``
  function (but you're free to send multiple concurrent requests with
  Lua scripts to Splash).

There are great PhantomJS wrappers like CasperJS_ and NightmareJS_ which
(among other things) bring a sync-looking syntax to PhantomJS scripts by
providing custom control flow mini-languages. However, they all have their
own gotchas and edge cases (loops? moving code to helper functions? error
handling?). Splash scripts are standard Lua code.

.. note::

    PhantomJS itself and its wrappers are great, they deserve lots of
    respect; please don't take this writeup as an attack on them.
    These tools are much more mature and feature complete than Splash.
    Splash tries to look at the problem from a different angle, but
    for each unique Splash feature there is an unique PhantomJS feature.

To read more about Splash Lua API features
check :ref:`splash-lua-api-overview`.

.. _CasperJS: http://casperjs.org/
.. _NightmareJS: http://www.nightmarejs.org/

Living Without Callbacks
------------------------

.. note::

    For the curious, Splash uses Lua coroutines under the hood.

    Internally, "main" function is executed as a coroutine by Splash,
    and some of the ``splash:foo()`` methods use ``coroutine.yield``.
    See http://www.lua.org/pil/9.html for Lua coroutines tutorial.

In Splash scripts it is not explicit which calls are async and which calls
are blocking; this is a common criticism of coroutines/greenlets. Check
`this <https://glyph.twistedmatrix.com/2014/02/unyielding.html>`__ article
for a good description of the problem.

However, these negatives have no real impact in Splash scripts which: are
meant to be small, where shared state is minimized, and the API is designed to
execute a single command at a time, so in most cases the control flow is linear.

If you want to be safe then think of all ``splash`` methods as async;
consider that after you call ``splash:foo()`` a webpage being
rendered can change. Often that's the point of calling a method,
e.g. ``splash:wait(time)`` or ``splash:go(url)`` only make sense because
webpage changes after calling them, but still - keep it in mind.

There are async methods like :ref:`splash-go`, :ref:`splash-wait`,
:ref:`splash-wait-for-resume`, etc.; most splash methods are currently
**not** async, but thinking of them as of async will allow your scripts
to work if we ever change that.

Calling Splash Methods
----------------------

Unlike in many languages, methods in Lua are usually separated from an object
using a colon ``:``; to call "foo" method of "splash" object use
``splash:foo()`` syntax. See http://www.lua.org/pil/16.html for more details.

There are two main ways to call Lua methods in Splash scripts:
using positional and named arguments. To call a method using positional
arguments use parentheses ``splash:foo(val1, val2)``, to call it with
named arguments use curly braces: ``splash:foo{name1=val1, name2=val2}``:

.. code-block:: lua

    -- Examples of positional arguments:
    splash:go("http://example.com")
    splash:wait(0.5, false)
    local title = splash:evaljs("document.title")

    -- The same using keyword arguments:
    splash:go{url="http://example.com"}
    splash:wait{time=0.5, cancel_on_redirect=false}
    local title = splash:evaljs{source="document.title"}

    -- Mixed arguments example:
    splash:wait{0.5, cancel_on_redirect=false}

For convenience all ``splash`` methods are designed to support both styles
of calling: positional and named. But since there are `no "real" named
arguments in Lua`_ most Lua functions (including the ones from the
standard library) choose to support just positional arguments.

.. _no "real" named arguments in Lua: http://www.lua.org/pil/5.3.html

Error Handling
--------------

There are two ways to report errors in Lua: raise an exception and return
an error flag. See http://www.lua.org/pil/8.3.html.

Splash uses the following convention:

1. for developer errors (e.g. incorrect function arguments) exception is raised;
2. for errors outside developer control (e.g. a non-responding remote website)
   status flag is returned: functions that can fail return ``ok, reason``
   pairs which developer can either handle or ignore.

If ``main`` results in an unhandled exception then Splash returns HTTP 400
response with an error message.

It is possible to raise an exception manually using Lua ``error`` function:

.. code-block:: lua

    error("A message to be returned in a HTTP 400 response")

To handle Lua exceptions (and prevent Splash from returning HTTP 400 response)
use Lua ``pcall``; see http://www.lua.org/pil/8.4.html.

To convert "status flag" errors to exceptions Lua ``assert`` function can be used.
For example, if you expect a website to work and don't want to handle errors
manually, then ``assert`` allows to stop processing and return HTTP 400
if the assumption is wrong:

.. code-block:: lua

    local ok, msg = splash:go("http://example.com")
    if not ok then
        -- handle error somehow, e.g.
        error(msg)
    end

    -- a shortcut for the code above: use assert
    assert(splash:go("http://example.com"))

.. _lua-sandbox:

Sandbox
-------

By default Splash scripts are executed in a restricted environment:
not all standard Lua modules and functions are available, Lua ``require``
is restricted, and there are resource limits (quite loose though).

To disable the sandbox start Splash with ``--disable-lua-sandbox`` option::

    $ docker run -it -p 8050:8050 scrapinghub/splash --disable-lua-sandbox

Timeouts
--------

By default Splash aborts script execution after a timeout
(30s by default); it is a common problem for long scripts.

For more information see :ref:`timeouts` and :ref:`504-slow-script`.

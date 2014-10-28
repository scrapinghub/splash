.. _scripts:

========================
Splash Rendering Scripts
========================

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


Tutorial
========

The script must provide "main" function; this function is called by Splash.
The result of this function is returned as a result of HTTP request call.
Script could contain other helper functions and statements; 'main'
is the only required.

For example, let's create a script that returns 'hello' string:

.. code-block:: lua

     function main(splash)
       return 'hello'
     end

We can now send this script in a `lua_source` argument and get a result back::

    $ curl 'http://127.0.0.1:8050/render.lua?lua_source=function+main%28splash%29%0D%0A++return+%27hello%27%0D%0Aend'
    hello

.. note::

    Instead of ``curl`` one can use Splash UI - it provides a code editor
    for Lua and a button to submit a script to ``render.lua``. Visit
    http://127.0.0.1:8050/ (or whatever host/port Splash is executed on).

"main" function can also return a Lua table (an associative array similar
to JavaScript Object or Python dict):

.. code-block:: lua

     function main(splash)
       -- this is a comment
       return {"hello": "world"}
     end

The result will be encoded to JSON in this case.

TODO

.. _splash-object:

splash object reference
=======================

A ``Splash`` instance is passed to ``main`` function; via this object
a script can control the browser.

Methods
-------

.. _splash-go:

ok, msg = splash:go(url[, baseurl])
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Go to url. This is similar to entering an URL in a browser
address tab, pressing Enter and waiting until page loads.

If ``ok`` is nil then error happened during page load, and ``msg`` contains
a description of the error.

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

ok, reason = splash:wait(time[, cancel_on_redirect=false, cancel_on_error=true])
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Wait for ``time`` seconds, then return ``true``.

If the timer was stopped prematurely then ``splash:wait`` returns
``ok==nil`` and a ``reason`` string with a reason.

If ``cancel_on_redirect`` is true (not a default) and a redirect
happened while waiting (for example, it could be initiated by JS code),
then ``splash:wait`` stops earlier and returns ``nil, "redirect"``.

If ``cancel_on_error`` is true (default) and an error which prevents page
from being rendered happened while waiting (e.g. an internal WebKit error
or a network error like a redirect to a non-resolvable host)
then ``splash:wait`` stops earlier and returns ``nil, "error"``.


Example:

.. code-block:: lua

     -- go to example.com, wait 0.5s, return rendered html, ignore all errors.
     function main(splash)
       splash:go("http://example.com")
       splash:wait(0.5)
       return {html=splash:html()}
     end


.. _splash-runjs:

result = splash:runjs(js_source)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Execute JavaScript in page context and return the result of the last statement.

.. code-block:: lua

    local title = splash:runjs("document.title")

TODO: more examples, document type conversions

.. _splash-html:

html = splash:html()
~~~~~~~~~~~~~~~~~~~~

Return a HTML snapshot of a current page (as a string).

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

.. _splash-set-result-content-type:

splash:set_result_content_type(content_type)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set Content-Type of a result returned to a client.

If a table is returned by "main" function then
``splash:set_result_content_type`` has no effect: Content-Type of the result
is set to ``application/json``.

This function **does not** set Content-Type header for requests
initiated by ``splash:go()``; this function is for setting Content-Type
header of a result.


Attributes
----------

TODO

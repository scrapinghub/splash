.. _scripting-reference:

Splash Scripts Reference
========================

A ``Splash`` instance is passed to ``main`` function; via this object
a script can control the browser.

.. _splash-go:

splash:go
---------

Go to url. This is similar to entering an URL in a browser
address bar, pressing Enter and waiting until page loads.

**Signature:** ``ok, msg = splash.go(url, baseurl=nil)``

**Parameters:**

* url - URL to load;
* baseurl - base URL to use. TODO: document me better.

**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
page load; ``reason`` provides an information about error type.

``ok`` can be ``nil`` in two cases (two types of errors are reported):

1. There is nothing to render. This can happen if a host doesn't exist,
   server dropped connection, etc. ``reason`` is ``"error"`` in this case.
2. Server returned a response with 4xx or 5xx HTTP status code.
   ``reason`` is "http<code>" in this case, e.g. for errors 404 ``reason``
   is ``"http404"``. This only applies to "main" webpage response; if a request
   to related resource returned 4xx or 5xx HTTP status code no error
   is reported.

Example:

.. code-block:: lua

    local ok, reason = splash:go("http://example.com")
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

**Returns:** the result of the last statement in ``source``,
converted from JavaScript to Lua data types.

Example:

.. code-block:: lua

    local title = splash:runjs("document.title")

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
Date            string (ISO8601 representation, e.g. ``1958-05-21T10:12:00Z``)
RegExp          table ``{_jstype='RegExp', caseSensitive=true/false, pattern='my-regexp'}``
function        an empty table ``{}`` (don't rely on it)
==============  =================


.. _splash-html:

splash:html
-----------

Return a HTML snapshot of a current page (as a string).

**Signature:** ``html = splash:html()``

**Returns:** contents of a current page (as a string).

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

**Signature:** ``png = splash:png(width=nil, height=nil)``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels.

**Returns:** PNG screenshot data.

TODO: document what default values mean

*width* and *height* arguments set a size of the resulting image,
not a size of an area screenshot is taken of. For example, if the viewport
is 1024px wide then ``splash:png{width=100}`` will return a screenshot
of the whole viewport, but an image will be downscaled to 100px width.

If the result of ``splash:png()`` returned directly as a result of
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

.. _HAR: http://www.softwareishard.com/blog/har-12-spec/


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

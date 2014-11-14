.. _scripting-reference:

Splash Scripts Reference
========================

``splash`` object is passed to ``main`` function; via this object
a script can control the browser. Think of it as of an API to
a single browser tab.

.. _splash-go:

splash:go
---------

Go to an URL. This is similar to entering an URL in a browser
address bar, pressing Enter and waiting until page loads.

**Signature:** ``ok, reason = splash.go{url, baseurl=nil}``

**Parameters:**

* url - URL to load;
* baseurl - base URL to use, optional. When ``baseurl`` argument is passed
  the page is still loaded from ``url``, but it is rendered as if it was
  loaded from ``baseurl``: relative resource paths will be relative
  to ``baseurl``, and the browser will think ``baseurl`` is in address bar.


**Returns:** ``ok, reason`` pair. If ``ok`` is nil then error happened during
page load; ``reason`` provides an information about error type.

Two types of errors are reported (``ok`` can be ``nil`` in two cases):

1. There is nothing to render. This can happen if a host doesn't exist,
   server dropped connection, etc. In this case ``reason`` is ``"error"``.
2. Server returned a response with 4xx or 5xx HTTP status code.
   ``reason`` is ``"http<code>"`` in this case, i.e. for
   HTTP 404 Not Found ``reason`` is ``"http404"``.

Error handling example:

.. code-block:: lua

    local ok, reason = splash:go("http://example.com")
    if not ok:
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
  then ``splash:wait`` stops earlier and returns ``nil, "error"``.

**Returns:** ``ok, reason`` pair. If ``ok`` is ``nil`` then the timer was
stopped prematurely, and ``reason`` contains a string with a reason.
Possible reasons are ``"error"`` and ``"redirect"``.

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


.. _splash-runjs:

splash:runjs
------------

Execute JavaScript in page context and return the result of the last statement.

**Signature:** ``result = splash:runjs(source)``

**Parameters:**

* source - a string with JavaScript source code to execute.

**Returns:** the result of the last statement in ``source``,
converted from JavaScript to Lua data types.

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


Example:

.. code-block:: lua

    local title = splash:runjs("document.title")

Lua ``[[ ]]`` string syntax is helpful for larger JavaScript scripts:

.. code-block:: lua

      local div_count = splash:runjs([[
          function getDivsCount(){
              var body = document.body;
              var divs = body.getElementsByTagName('div');
              return divs.length;
          }

          getDivsCount();
      ]])

Currently to pass data to JavaScript code you need to use string formatting;
this will be improved in future releases:

.. code-block:: lua

    -- Lua function to scroll window to (x, y) position.
    function scroll_to(splash, x, y)
        local js = string.format(
            "window.scrollTo(%s, %s);",
            tonumber(x),
            tonumber(y)
        )
        return splash:runjs(js)
    end


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

**Signature:** ``png = splash:png{width=nil, height=nil}``

**Parameters:**

* width - optional, width of a screenshot in pixels;
* height - optional, height of a screenshot in pixels.

**Returns:** PNG screenshot data.

TODO: document what default values mean

*width* and *height* arguments set a size of the resulting image,
not a size of an area screenshot is taken of. For example, if the viewport
is 1024px wide then ``splash:png{width=100}`` will return a screenshot
of the whole viewport, but an image will be downscaled to 100px width.

To set the viewport size use :ref:`splash-set-viewport` method.

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


.. _splash-history:

splash:history
--------------

**Signature:** ``entries = splash:history()``

**Returns:** information about requests/responses for the pages loaded, in
`HAR entries`_ format.

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

.. _splash-set-images-enabled:

splash:set_images_enabled
-------------------------

Enable/disable images.

**Signature:** ``splash:set_images_enabled(enabled)``

**Parameters:**

* enabled - ``true`` to enable images, ``false`` to disable them.

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
         splash:set_images_enabled(false)
         assert(splash:go("http://example.com"))
         return {png=splash:png()}
     end


.. _splash-set-viewport:

splash:set_viewport
-------------------

Set the browser viewport.

**Signature:** ``width, height = splash:set_viewport(size)``

**Parameters:**

* size - string, width and height of the viewport.
  Format is ``"<width>x<heigth>"``, e.g. ``"800x600"``.
  It also accepts ``"full"`` as a value; ``"full"`` means that the viewport size
  will be auto-detected to fit the whole page (possibly very tall).

**Returns:** two numbers: width and height the viewport is set to, in pixels.

``splash:set_viewport("full")`` should be called only after page
is loaded, and some time passed after that (use :ref:`splash-wait`). This is
an unfortunate restriction, but it seems that this is the only
way to make rendering work reliably with size="full".

:ref:`splash-png` uses the viewport size.

Example:

.. code-block:: lua

     function main(splash)
         assert(splash:go("http://example.com"))
         assert(splash:wait(0.5))
         splash:set_viewport("full")
         return {png=splash:png()}
     end

.. _splash-args:

splash.args
-----------

``splash.args`` is a table with incoming parameters. It contains
merged values from the orignal URL string (GET arguments) and
values sent using ``application/json`` POST request.

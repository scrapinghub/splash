.. _binary-data:

Working with Binary Data
========================

Motivation
----------

Splash assumes that most strings in a script are encoded to UTF-8.
This is true for HTML content - even if the original response was not UTF-8,
internally browser works with UTF-8, so :ref:`splash-html` result is always
UTF-8.

When you return a Lua table from the ``main`` function Splash encodes it
to JSON; JSON is a text protocol which can't handle arbitrary binary data,
so Splash assumes all strings are UTF-8 when returning a JSON result.

But sometimes it is necessary to work with binary data: for example,
it could be raw image data returned by :ref:`splash-png` or a response
body of a non-UTF-8 page returned by :ref:`splash-http-get`.

.. _binary-objects:

Binary Objects
--------------

To pass non-UTF8 data to Splash (returning it as a result of ``main`` or
passing as arguments to ``splash`` methods) a script may mark it as
a binary object using :ref:`treat-as-binary` function.

Some of the Splash functions already return binary objects: :ref:`splash-png`,
:ref:`splash-jpeg`; :ref:`splash-response-body` attribute is also
a binary object.

A binary object can be returned as a ``main`` result directly.
It is the reason the following example works
(a basic :ref:`render.png` implementation in Lua):

.. code-block:: lua

    -- basic render.png emulation
    function main(splash)
        assert(splash:go(splash.args.url))
        return splash:png()
    end

All binary objects have content-type attached. For example, :ref:`splash-png`
result will have content-type ``image/png``.

When returned directly, a binary object data is used as-is for the
response body, and Content-Type HTTP header is set to the content-type
of a binary object. So in the previous example the result will be a PNG image
with a proper Content-Type header.

To construct your own binary objects use :ref:`treat-as-binary` function.
For example, let's return a 1x1px black GIF image as a response:

.. code-block:: lua

    treat = require("treat")
    base64 = require("base64")

    function main(splash)
        local gif_b64 = "AQABAIAAAAAAAAAAACH5BAAAAAAALAAAAAABAAEAAAICTAEAOw=="
        local gif_bytes = base64.decode(gif_b64)
        return treat.as_binary(gif_bytes, "image/gif")
    end

When ``main`` result is returned, binary object content-type takes a priority
over a value set by :ref:`splash-set-result-content-type`. To override
content-type of a binary object create another binary object with a required
content-type:

.. code-block:: lua

    lcoal treat = require("treat")
    function main(splash)
        -- ...
        local img = splash:png()
        return treat.as_binary(img, "image/x-png") -- default was "image/png"
    end

When a binary object is serialized to JSON it is auto-encoded to base64
before serializing. For example, it may happen when a table is returned
as a ``main`` function result:

.. code-block:: lua

    function main(splash)
        assert(splash:go(splash.args.url))

        -- result is a JSON object {"png": "...base64-encoded image data"}
        return {png=splash:png()}
    end

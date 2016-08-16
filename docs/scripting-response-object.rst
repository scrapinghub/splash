.. _splash-response:

Response Object
===============

Response objects are returned as a result of several Splash methods
(like :ref:`splash-http-get` or :ref:`splash-http-post`); they are
are also passed to some of the callbacks (e.g. :ref:`splash-on-response` and
:ref:`splash-on-response-headers` callbacks). These objects contain
information about a response.

.. _splash-response-url:

response.url
------------

URL of the response. In case of redirects :ref:`splash-response-url`
is a last URL.

This field is read-only.

.. _splash-response-status:

response.status
---------------

HTTP status code of the response.

This field is read-only.

.. _splash-response-ok:

response.ok
-----------

``true`` for successful responses and ``false`` when error happened.

Example:

.. code-block:: lua

    local reply = splash:http_get("some-bad-url")
    -- reply.ok == false

This field is read-only.

.. _splash-response-headers:

response.headers
----------------

A Lua table with HTTP headers (header name => header value).
Keys are header names (strings), values are header values (strings).

Lookups are case-insensitive, so ``response.headers['content-type']``
is the same as ``response.headers['Content-Type']``.

This field is read-only.

.. _splash-response-info:

response.info
-------------

A Lua table with response data in `HAR response`_ format.

This field is read-only.

.. _HAR response: http://www.softwareishard.com/blog/har-12-spec/#response

.. _splash-response-body:

response.body
-------------

Raw response body (a :ref:`binary object <binary-objects>`).

If you want to process response body from Lua use :ref:`treat-as-string`
to convert it to a Lua string first.

:ref:`splash-response-body` attribute is not available by default
in :ref:`splash-on-response` callbacks; use :ref:`splash-response-body-enabled`
or :ref:`splash-request-enable-response-body` to enable it.

.. _splash-response-request:

response.request
----------------

A corresponding :ref:`splash-request`.

This field is read-only.

.. _splash-response-abort:

response:abort
--------------

**Signature:** ``response:abort()``

**Returns:** nil.

**Async:** no.

Abort reading of the response body. This method is only available if
a response is not read yet - currently you can use it only
in a :ref:`splash-on-response-headers` callback.


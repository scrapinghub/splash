.. _splash-request:

Request Object
==============

Request objects are received by :ref:`splash-on-request` callbacks;
they are also available as :ref:`response.request <splash-response-request>`.

.. _splash-request-attributes:

Attributes
~~~~~~~~~~

Request objects has several attributes with information about a HTTP request.
These fields are for information only; changing them doesn't change
the request to be sent.

.. _splash-request-url:

request.url
-----------

Requested URL.

.. _splash-request-method:

request.method
--------------

HTTP method name in upper case, e.g. "GET".

.. _splash-request-headers:

request.headers
---------------

A Lua table with request HTTP headers (header name => header value).
Keys are header names (strings), values are header values (strings).

Lookups are case-insensitive, so ``request.headers['content-type']``
is the same as ``request.headers['Content-Type']``.


.. _splash-request-info:

request.info
------------

A table with request data in `HAR request`_ format.

.. _HAR request: http://www.softwareishard.com/blog/har-12-spec/#request


.. _splash-request-methods:

Methods
~~~~~~~

To change or drop the request before sending use one of
the ``request`` methods. Note that these methods are only available
before the request is sent (they has no effect if a request is already sent).
Currently it means you can only use them in :ref:`splash-on-request` callbacks.

.. _splash-request-abort:

request:abort
-------------

Drop the request.

**Signature:** ``request:abort()``

**Returns:** nil.

**Async:** no.

.. _splash-request-enable-response-body:

request:enable_response_body
----------------------------

Enable tracking of response content (i.e. :ref:`splash-response-body`
attribute).

**Signature:** ``request:enable_response_body()``

**Returns:** nil.

**Async:** no.

This function allows to enable response content tracking per-request
when :ref:`splash-response-body-enabled` is set to false.
Call it in a :ref:`splash-on-request` callback.

.. _splash-request-set-url:

request:set_url
---------------

Change request URL to a specified value.

**Signature:** ``request:set_url(url)``

**Parameters:**

* url - new request URL

**Returns:** nil.

**Async:** no.


.. _splash-request-set-proxy:

request:set_proxy
-----------------

Set a proxy server to use for this request.

**Signature:** ``request:set_proxy{host, port, username=nil, password=nil, type='HTTP'}``

**Parameters:**

* host
* port
* username
* password
* type - proxy type; allowed proxy types are 'HTTP' and 'SOCKS5'.

**Returns:** nil.

**Async:** no.

Omit ``username`` and ``password`` arguments if a proxy
doesn't need auth.

When ``type`` is set to 'HTTP' HTTPS proxying should
also work; it is implemented using CONNECT command.


.. _splash-request-set-timeout:

request:set_timeout
-------------------

Set a timeout for this request.

**Signature:** ``request:set_timeout(timeout)``

**Parameters:**

* timeout - timeout value, in seconds.

**Returns:** nil.

**Async:** no.

If response is not fully received after the timeout,
request is aborted. See also: :ref:`splash-resource-timeout`.

.. _splash-request-set-header:

request:set_header
------------------

Set an HTTP header for this request.

**Signature:** ``request:set_header(name, value)``

**Parameters:**

* name - header name;
* value - header value.

**Returns:** nil.

**Async:** no.

See also: :ref:`splash-set-custom-headers`

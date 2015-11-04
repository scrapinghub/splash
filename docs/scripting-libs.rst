.. _scripting-libs:

Available Lua Libraries
=======================

When :ref:`Sandbox <lua-sandbox>` is disabled all standard Lua modules
are available; with a Sandbox ON (default) only some of them can be used.
See :ref:`lib-standard` for more.

Splash ships several non-standard modules by default:

* :ref:`lib-json` - encoded/decode JSON data
* :ref:`lib-base64` - encode/decode Base64 data
* :ref:`lib-treat` - fine-tune the way Splash works with your Lua varaibles
  and returns the result.

Unlike standard modules, custom modules should to be imported before use,
for example:

.. code-block:: lua

    base64 = require("base64")
    function main(splash)
        return base64.encode('hello')
    end

It is possible to add more Lua libraries to Splash using
:ref:`Custom Lua Modules <custom-lua-modules>` feature.


.. _lib-standard:

Standard Library
~~~~~~~~~~~~~~~~

The following standard Lua 5.2 libraries are available
to Splash scripts when Sandbox is enabled (default):

* `string <http://www.lua.org/manual/5.2/manual.html#6.4>`_
* `table <http://www.lua.org/manual/5.2/manual.html#6.5>`_
* `math <http://www.lua.org/manual/5.2/manual.html#6.6>`_
* `os <http://www.lua.org/manual/5.2/manual.html#6.9>`_

Aforementioned libraries are pre-imported; there is no need to ``require`` them.

.. note::

    Not all functions from these libraries are currently exposed
    when :ref:`Sandbox <lua-sandbox>` is enabled.


.. _lib-json:

json
~~~~

A library to encode data to JSON and decode it from JSON to Lua data
structure. It provides 2 functions: :ref:`json-encode`
and :ref:`json-decode`.

.. _json-encode:

json.encode
-----------

Encode data to JSON.

**Signature:** ``result = json.encode(obj)``

**Parameters:**

* obj - an object to encode.

**Returns:** a string with JSON representation of ``obj``.

JSON format doesn't support binary data; json.encode handles
:ref:`binary-objects` by automatically encoding them
to Base64 before putting to JSON.

.. _json-decode:

json.decode
-----------

Decode JSON string to a Lua object.

**Signature:** ``decoded = json.decode(s)``

**Parameters:**

* s - a string with JSON.

**Returns:** decoded Lua object.

Example:

.. code-block:: lua

    json = require("json")

    function main(splash)
        local resp = splash:http_get("http:/myapi.example.com/resource.json")
        local decoded = json.decode(resp.content.text)
        return {myfield=decoded.myfield}
    end

Note that unlike :ref:`json-encode` function, :ref:`json-decode`
doesn't have any special features to support :ref:`binary data <binary-data>`.
It means that if you want to get a binary object encoded by
:ref:`json-encode` back, you need to decode data from base64 yourselves.
This can be done in a Lua script using :ref:`lib-base64` module.

.. _lib-base64:

base64
~~~~~~

A library to encode/decode strings to/from Base64. It provides 2 functions:
:ref:`base64-encode` and :ref:`base64-decode`. These functions are
handy if you need to pass some binary data in a JSON request or response.

.. _base64-encode:

base64.encode
-------------

Encode a string or a :ref:`binary object <binary-objects>` to Base64.

**Signature:** ``encoded = base64.encode(s)``

**Parameters:**

* s - a string or a :ref:`binary object <binary-objects>` to encode.

**Returns:** a string with Base64 representation of ``s``.


.. _base64-decode:

base64.decode
-------------

Decode a string from base64.

**Signature:** ``data = base64.decode(s)``

**Parameters:**

* s - a string to decode.

**Returns:** a Lua string with decoded data.

Note that base64.decode may return a non-UTF-8 Lua string, so the result
may be unsafe to pass back to Splash (as a part of ``main`` function result
or as an argument to ``splash`` methods). It is fine if you know the original
data was ASCII or UTF8, but if you work with unknown data, "real" binary
data or just non-UTF-8 content then call :ref:`treat-as-binary` on the result
of :ref:`base64-decode`.

Example - return 1x1px black gif:

.. code-block:: lua

    treat = require("treat")
    base64 = require("base64")

    function main(splash)
        local gif_b64 = "AQABAIAAAAAAAAAAACH5BAAAAAAALAAAAAABAAEAAAICTAEAOw=="
        local gif_bytes = base64.decode(gif_b64)
        return treat.as_binary(gif_bytes, "image/gif")
    end


.. _lib-treat:

treat
~~~~~

.. _treat-as-binary:

treat.as_binary
---------------

Get a :ref:`binary object <binary-objects>` for a string.

**Signature:** ``bytes = treat.as_binary(s, content_type="application/octet-stream")``

**Parameters:**

* s - a string.
* content-type - Content-Type of ``s``.

**Returns:** a :ref:`binary object <binary-objects>`.

:ref:`treat-as-binary` returns a binary object for a string. This binary
object no longer can be processed from Lua, but it can be
returned as a main() result as-is.


.. _treat-as-string:

treat.as_string
---------------

Get a Lua string with a raw data from a :ref:`binary object <binary-objects>`.

**Signature:** ``s, content_type = treat.as_string(bytes)``

**Parameters:**

* bytes - a :ref:`binary object <binary-objects>`.

**Returns:** ``(s, content_type)`` pair: a Lua string with raw data and
its Content-Type.

:ref:`treat-as-string` "unwraps" a :ref:`binary object <binary-objects>` and
returns a plain Lua string which can be processed from Lua.
If the resulting string is not encoded to UTF-8 then it is still possible to
process it in Lua, but it is not safe to return it as a ``main`` result
or pass to Splash functions. Use :ref:`treat-as-binary` to convert
processed string to a binary object if you need to pass it back to Splash.

.. _treat-as-array:

treat.as_array
--------------

Mark a Lua table as an array (for JSON encoding and Lua -> JS conversions).

**Signature:** ``tbl = treat.as_array(tbl)``

**Parameters:**

* tbl - a Lua table.

**Returns:** the same table.

JSON can represent arrays and objects, but in Lua there is no distinction
between them; both key-value mappings and arrays are stored in Lua tables.

By default, Lua tables are converted to JSON objects when returning a result
from Splash ``main`` function and when using :ref:`json-encode`
or ref:`splash-jsfunc`:

.. code-block:: lua

    function main(splash)
        -- client gets {"foo": "bar"} JSON object
        return {foo="bar"}
    end

It can lead to unexpected results with array-like Lua tables:

.. code-block:: lua

    function main(splash)
        -- client gets {"1": "foo", "2": "bar"} JSON object
        return {"foo", "bar"}
    end

:ref:`treat-as-array` allows to mark tables as JSON arrays:

.. code-block:: lua

    treat = require("treat")

    function main(splash)
        local tbl = {"foo", "bar"}
        treat.as_array(tbl)

        -- client gets ["foo", "bar"] JSON object
        return tbl
    end

**This function modifies its argument inplace**, but as a shortcut it returns
the same table; it allows to simplify the code:

.. code-block:: lua

    treat = require("treat")
    function main(splash)
        -- client gets ["foo", "bar"] JSON object
        return treat.as_array({"foo", "bar"})
    end

.. note::

    There is no autodetection of table type because ``{}`` Lua table
    is ambiguous: it can be either a JSON array or as a JSON object.
    With table type autodetection it is easy to get a wrong output:
    even if some data is always an array, it can be suddenly exported
    as an object when an array is empty. To avoid surprises Splash requires
    an explicit :ref:`treat-as-array` call.


.. _custom-lua-modules:

Adding Your Own Modules
~~~~~~~~~~~~~~~~~~~~~~~

Splash provides a way to use custom Lua modules (stored on server)
from scripts passed via HTTP API. This allows to

1. reuse code without sending it over network again and again;
2. use third-party Lua modules;
3. implement features which need unsafe code and expose them safely
   in a sandbox.

.. note::

    To learn about Lua modules check e.g. http://lua-users.org/wiki/ModulesTutorial.
    Please prefer "the new way" of writing modules because it plays better
    with a sandbox. A good Lua modules style guide can be found here:
    http://hisham.hm/2014/01/02/how-to-write-lua-modules-in-a-post-module-world/


Setting Up
----------

To use custom Lua modules, do the following steps:

1. setup the path for Lua modules and add your modules there;
2. tell Splash which modules are enabled in a sandbox;
3. use Lua ``require`` function from a script to load a module.

To setup the path for Lua modules start Splash with ``--lua-package-path``
option. ``--lua-package-path`` value should be a semicolon-separated list
of places where Lua looks for modules. Each entry should have a ? in it
that's replaced with the module name.

Example::

    $ python -m splash.server --lua-package-path "/etc/splash/lua_modules/?.lua;/home/myuser/splash-modules/?.lua"

.. note::

    If you use Splash installed using Docker see
    :ref:`docker-folder-sharing` for more info on how to setup
    paths.

.. note::

    For the curious: ``--lua-package-path`` value is added to Lua
    ``package.path``.

When you use a :ref:`Lua sandbox <lua-sandbox>` (default) Lua ``require``
function is restricted when used in scripts: it only allows to load
modules from a whitelist. This whitelist is empty by default, i.e. by default
you can require nothing. To make your modules available for scripts start
Splash with ``--lua-sandbox-allowed-modules`` option. It should contain a
semicolon-separated list of Lua module names allowed in a sandbox::

    $ python -m splash.server --lua-sandbox-allowed-modules "foo;bar" --lua-package-path "/etc/splash/lua_modules/?.lua"

After that it becomes possible to load these modules from Lua scripts using
``require``:

.. code-block:: lua

    local foo = require("foo")
    function main(splash)
        return {result=foo.myfunc()}
    end


Writing Modules
---------------

A basic module could look like the following:

.. code-block:: lua

    -- mymodule.lua
    local mymodule = {}

    function mymodule.hello(name)
        return "Hello, " .. name
    end

    return mymodule

Usage in a script:

.. code-block:: lua

    local mymodule = require("mymodule")

    function main(splash)
        return mymodule.hello("world!")
    end

Many real-world modules will likely want to use ``splash`` object.
There are several ways to write such modules. The simplest way is to use
functions that accept ``splash`` as an argument:

.. code-block:: lua

    -- utils.lua
    local utils = {}

    -- wait until `condition` function returns true
    function utils.wait_for(splash, condition)
        while not condition() do
            splash:wait(0.05)
        end
    end

    return utils

Usage:

.. code-block:: lua

    local utils = require("utils")

    function main(splash)
        splash:go(splash.args.url)

        -- wait until <h1> element is loaded
        utils.wait_for(splash, function()
           return splash:evaljs("document.querySelector('h1') != null")
        end)

        return splash:html()
    end

Another way to write such module is to add a method to ``splash``
object. This can be done by adding a method to its ``Splash``
class - the approach is called "open classes" in Ruby or "monkey-patching"
in Python.

.. code-block:: lua

    -- wait_for.lua

    -- Sandbox is not enforced in custom modules, so we can import
    -- internal Splash class and change it - add a method.
    local Splash = require("splash")

    function Splash:wait_for(condition)
        while not condition() do
            self:wait(0.05)
        end
    end

    -- no need to return anything

Usage:

.. code-block:: lua

    require("wait_for")

    function main(splash)
        splash:go(splash.args.url)

        -- wait until <h1> element is loaded
        splash:wait_for(function()
           return splash:evaljs("document.querySelector('h1') != null")
        end)

        return splash:html()
    end

Which style to prefer is up to the developer. Functions are more explicit
and composable, monkey patching enables a more compact code. Either way,
``require`` is explicit.

As seen in a previous example, sandbox restrictions for standard Lua modules
and functions **are not applied** in custom Lua modules, i.e. you can use
all the Lua powers. This makes it possible to import third-party Lua modules
and implement advanced features, but requires developer to be careful.
For example, let's use `os <http://www.lua.org/manual/5.2/manual.html#6.9>`__
module:

.. code-block:: lua

    -- evil.lua
    local os = require("os")
    local evil = {}

    function evil.sleep()
        -- Don't do this! It blocks the event loop and has a startup cost.
        -- splash:wait is there for a reason.
        os.execute("sleep 2")
    end

    function evil.touch(filename)
        -- another bad idea
        os.execute("touch " .. filename)
    end

    -- todo: rm -rf /

    return evil

JavaScript <-> Python <-> Lua intergation
=========================================

Lua and JavaScript are not connected directly; they communicate through Python.

Python <-> Lua is handled using lupa library.
:func:`splash.qtrender_lua.command` decorator handles most of Python <-> Lua
integration.

Python <-> JavaScript is handled using custom serialization code.
QT host objects are not used (with a few exceptions). Instead of this
JavaScript results are sanitized and processed in Python;
Python results are encoded to JSON and decoded/processed
in JavaScript.

Python -> Lua
-------------

Data is converted from Python to Lua in two cases:

1. method of an exposed Python object returns a result
   (most common example is a method of ``splash`` Lua object);
2. Python code calls Lua function with arguments - it could be e.g.
   an on_request callback.

Conversion rules:

* Basic Python types are converted to Lua: strings -> Lua strings,
  lists and dicts -> Lua tables, numbers -> Lua numbers, None -> nil(?).

  This is handled using :meth:`splash.lua_runtime.SplashLuaRuntime.python2lua`
  method. For attributes exposed to Lua this method is called manually;
  for return results of Python functions / methods it is handled by
  :func:`splash.qtrender_lua.emits_lua_objects` decorator. Methods decorated
  with ``@command`` use ``splash.qtrender_lua.emits_lua_objects`` internally,
  so a Python method decorated with ``@command`` decorator may return Python
  result in its body, and the final result would be a Lua object.

* If there is a need to expose a custom Python object to Lua then
  a subclass of :class:`splash.qtrender_lua.BaseExposedObject` is used; it is
  wrapped to a Lua table using utilities from wraputils.lua.
  Lua table exposes whitelisted attributes and methods of the object
  using metatable, and disallows access to all other attributes.

* Other than that, there is no automatic conversion. If something is not
  converted then it is available for Lua as an opaque userdata object;
  access to methods and attributes is disabled by a sandbox.

* To prevent wrapping method may return :class:`splash.lua.PyResult` instance.


Lua -> Python
-------------

Lua -> Python conversion is needed in two cases:

1. Lua code calls Python code, passing some arguments;
2. Python code calls Lua code and wants a result back.

* Basic Lua types are converted to Python using
  :meth:`splash.lua_runtime.SplashLuaRuntime.lua2python`. For method arguments
  lua2python is called by :func:`splash.qtrender_lua.decodes_lua_arguments`
  decorator; ``@command`` decorator uses ``decodes_lua_arguments`` internally.

* Python objects which were exposed to Lua (BaseExposedObject subclasses)
  are **not** converted back. By default they raise an error;
  with decode_arguments=False they are available as opaque
  Lua (lupa) table objects.

  :func:`splash.qtrender_lua.is_wrapped_exposed_object` can be used to check
  if a lupa object is a wrapped BaseExposedObject instance; obj.unwrapped()
  method can be used to access the underlying Python object.


JavaScript -> Python
--------------------

To get results from JavaScript to Python they are converted to primitive
JSON-serializable types first. QtWebKit host objects are not used.
Objects of unknown JavaScript types are discared, max depth of result
is limited.

JavaScript -> Python conversion utilities reside in

* :mod:`splash.jsutils` module - JavaScript side, i.e. sanitizing and encoding;
  two main functions are ``SANITIZE_FUNC_JS`` and ``STORE_DOM_ELEMENTS_JS``;
* :meth:`splash.browser_tab.BrowserTab.evaljs` method - Python side,
  i.e. decoding of the result.

For most types (objects, arrays, numbers, strings) conversion method
is straightforward; the most tricky case is a reference to DOM nodes.

For top-level DOM nodes (i.e. a result is a DOM node or a NodeList)
a node is stored in a special window attribute, and generated id is returned
to Python instead. All other DOM nodes are discarded - returning a Node
or a NodeList as a part of data structure is not supported at the moment.
``STORE_DOM_ELEMENTS_JS`` processes Node and NodeList objects;
``SANITIZE_FUNC_JS`` sanitizes the result (handles all other data types,
drops unsupported data).

In Python HTMLElement objects are created for DOM nodes; they contain node_id
attribute with id returned by JavaScript; it allows to fetch the real Node
object in JavaScript. This is handled by
:meth:`splash.browser_tab.BrowserTab.evaljs`.

Python -> JavaScript
--------------------

There are two cases Python objects are converted to JavaScript objects:

1. functions created with splash:jsfunc() are called with arguments;
2. methods of HtmlElement which wrap JS functions are called with arguments.

The conversion is handled either by :func:`splash.html_element.escape_js_args`
or by :func:`splash.jsutils.escape_js`.

* ``escape_js`` just encodes Python data to JSON and removes quotes; the result
  can be used as literal representation of argument values, i.e. added to
  a JS function call using string formatting.
* ``escape_js_args`` is similar to ``escape_js``, but it handles
  ``splash.html_element.HTMLElement`` instances by replacing them with JS
  code to access stored nodes.

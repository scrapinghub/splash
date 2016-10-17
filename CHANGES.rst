Changes
=======

2.2.1 (2016-10-17)
------------------

This is a bug fix release:

* fix Splash UI in Chrome when serving from localhost;
* upgrade adblockparser to 0.7 to support recent easylist filters;
* upgrade Pillow to 3.3.3.

2.2 (2016-09-10)
----------------

New features:

* new :ref:`splash-send-keys` and :ref:`splash-send-text` methods allow to
  send native keyboard events to browser;
* new :ref:`splash-with-timeout` method allows to limit execution time of
  blocks of code;
* new :ref:`splash-plugins-enabled` attribute which allows to enable Flash;
  Flash is now available in Docker image, but it is still disabled by default.
* new :ref:`splash-response-body-enabled` attribute,
  :ref:`splash-request-enable-response-body` method and
  :ref:`response_body <arg-response-body>` argument allows to access
  and export response bodies.

Bug fixes:

* fixed handling of :ref:`splash-call-later`, :ref:`splash-on-request`,
  :ref:`splash-on-response` and :ref:`splash-on-response-headers`
  callback arguments;
* fixed cleanup of various callbacks;
* fixed :ref:`save_args <arg-save-args>` in Python 2.x;

Other changes:

* internal cleanup of Lua <-> Python interaction;
* Pillow library is updated in Docker image;
* HarViewer is upgraded to a recent version.

2.1 (2016-04-20)
----------------

New features:

* 'region' argument for :ref:`splash-png` and :ref:`splash-jpeg` methods
  allow to take screenshots of parts of pages;
* :ref:`save_args <arg-save-args>` and :ref:`load_args <arg-load-args>`
  parameters allow to save network traffic by caching large request arguments
  inside Splash server;
* new :ref:`splash-mouse-click`, :ref:`splash-mouse-press`,
  :ref:`splash-mouse-release` and :ref:`splash-mouse-hover` methods for sending
  mouse events to web pages.

Bug fixes:

* User-Agent is set correctly for requests with baseurl;
* "download" links in Splash UI are fixed;
* an issue with ad blockers preventing Splash UI to work is fixed.

2.0.3 (2016-03-04)
------------------

This is a bugfix release:

* Splash Notebook is fixed to work with recent ipykernel versions;
* segfaults in adblock middleware are fixed;
* adblock parsing issues are fixed by upgrading adblockparser to v0.5;
* fixed handling of adblock rules with 'domain' option: domain is now
  extracted from the page URL, not necessarily from 'url' Splash argument.

2.0.2 (2016-02-26)
------------------

This is a bugfix release:

* an issue which may cause segfaults is fixed.

2.0.1 (2016-02-25)
------------------

This is a bugfix release:

* XSS in HTTP UI is fixed;
* Splash-Jupyter docker image is fixed.

2.0 (2016-02-21)
----------------

Splash 2.0 uses Qt 5.5.1 instead of Qt 4; it means the rendering
engine now supports more HTML5 features and is more modern overall.
Also, the official Docker image now uses Python 3 instead of Python 2.
This work is largely done by Tarashish Mishra as a Google Summer of Code 2015
project.

Splash 2.0 release introduces other cool new features:

* many Splash HTTP UI improvements;
* better support for :ref:`binary data <binary-data>`;
* built-in :ref:`lib-json` and :ref:`lib-base64` libraries;
* more :ref:`control <lib-treat>` for result serialization
  (support for JSON arrays and raw bytes);
* it is now possible to turn Private mode OFF at startup using command-line
  option or at runtime using :ref:`splash-private-mode-enabled` attribute;
* :ref:`http-ping` endpoint is added;
* cookie handling is fixed;
* downloader efficiency is improved;
* request processing is stopped when client disconnects;
* logging inside callbacks now uses proper verbosity;
* sandbox memory limit for user objects is increased to 50MB;
* some sandboxing issues are fixed;
* :ref:`splash-evaljs` and :ref:`splash-jsfunc` results are sanitized better;
* it is possible to pass arguments when starting Splash-Jupyter - it means
  now you can get a browser window for splash-jupyter when it is executed
  from docker;
* proxy authentication is fixed;
* logging improvements: logs now contain request arguments in JSON format;
  errors are logged;

There are **backwards-incompatible** changes
to :ref:`Splash Scripting <scripting-tutorial>`: previously, different
Splash methods were returning/receiving inconsistent
response and request objects. For example, :ref:`splash-http-get` response was
not in the same format as ``response`` received by :ref:`splash-on-response`
callbacks. Splash 2.0 uses :ref:`Request <splash-request>` and
:ref:`Response <splash-response>` objects consistently.
Unfortunately this requires changes to existing user scripts:

* replace ``resp = splash:http_get(...)`` and ``resp = splash:http_post(...)``
  with ``resp = splash:http_get(...).info`` and
  ``resp = splash:http_post(...).info``. Client code also may need to be
  changed: the default encoding of ``info['content']['text']`` is now base64.
  If you used ``resp.content.text`` consider switching to
  :ref:`splash-response-body`.

* ``response`` object received by :ref:`splash-on-response-headers` and
  :ref:`splash-on-response` callbacks is changed: instead of
  ``response.request`` write ``response.request.info``.

Serialization of JS objects in :ref:`splash-jsfunc`, :ref:`splash-evaljs`
and :ref:`splash-wait-for-resume` **is changed**: circular objects are
no longer returned, Splash doesn't try to serialize DOM elements, and error
messages are changed.

Splash **no longer supports** QT-based disk cache; it was disable by default
and it usage was discouraged since Splash 1.0, in Splash 2.0 ``--cache``
command-line option is removed. For HTTP cache there are better options like
`Squid <http://www.squid-cache.org/>`_.

Another **backwards-incompatible** change is that Splash-as-a-proxy feature
is removed. Please use regular HTTP API instead of this proxy interface.
Of course, Splash will still support using proxies to make requests,
these are two different features.


1.8 (2015-09-29)
----------------

New features:

* POST requests support: :ref:`http_method <arg-http-method>` and
  :ref:`body <arg-body>` arguments for render endpoints;
  new :ref:`splash-go` arguments: ``body``, ``http_method`` and ``formdata``;
  new :ref:`splash-http-post` method.
* Errors are now returned in JSON format; error mesages became more detailed;
  Splash UI now displays detailed error information.
* new :ref:`splash-call-later` method which allows to schedule tasks in future;
* new :ref:`splash-on-response` method allows to register a callback to be
  executed after each response;
* proxy can now be set directly, without using proxy profiles - there is a new
  :ref:`proxy <arg-proxy>` argument for render endpoints;
* more detailed :ref:`splash-go` errors: a new "render_error" error type can
  be reported;
* new :ref:`splash-set-result-status-code` method;
* new :ref:`splash-resource-timeout` attribute as a shortcut for
  ``request:set_timeout`` in :ref:`splash-on-request`;
* new :ref:`splash-get-version` method;
* new :ref:`splash-autoload-reset`, :ref:`splash-on-response-reset`,
  :ref:`splash-on-request-reset`, :ref:`splash-on-response-headers-reset`,
  :ref:`splash-har-reset` methods and a new ``reset=true`` argument for
  :ref:`splash-har`. They are most useful with Splash-Jupyter.

Bug fixes and improvements:

* fixed an issue: proxies were not applied for POST requests;
* improved argument validation for various methods;
* more detailed logs;
* it is now possible to load a combatibility shim for window.localStorage;
* code coverage integration;
* improved Splash-Jupyter tests;
* Splash-Jupyter is upgraded to Jupyter 4.0.

1.7 (2015-08-06)
----------------

New features:

* :ref:`render.jpeg` endpoint and :ref:`splash-jpeg` function allow to take
  screenshots in JPEG format;
* :ref:`splash-on-response-headers` Lua function and
  :ref:`allowed_content_types <arg-allowed-content-types>` /
  :ref:`forbidden_content_types <arg-forbidden-content-types>` HTTP arguments
  allow to discard responses earlier based on their headers;
* :ref:`splash-images-enabled` attribute to enable/disable images from
  Lua scripts;
* :ref:`splash-js-enabled` attribute to enable/disable JS processing from
  Lua scripts;
* :ref:`splash-set-result-header` method for setting custom HTTP headers
  returned to Splash clients;
* :ref:`resource_timeout <arg-resource-timeout>` argument for setting network
  request timeouts in render endpoints;
* ``request:set_timeout(timeout)`` method (ses :ref:`splash-on-request`)
  for setting request timeouts from Lua scripts;
* SOCKS5 proxy support: new 'type' argument
  in :ref:`proxy profile <proxy profiles>` config files
  and ``request:set_proxy`` method (ses :ref:`splash-on-request`)
* enabled HTTPS proxying;

Other changes:

* HTTP error detection is improved;
* MS fonts are added to the Docker image for better rendering quality;
* Chinese fonts are added to the Docker image to enable rendering of Chinese
  websites;
* validation of ``timeout`` and ``wait`` arguments is improved;
* documentation: grammar is fixed in the tutorial;
* assorted documentation improvements and code cleanups;
* ``splash:set_images_enabled`` method is deprecated.


1.6 (2015-05-15)
----------------

The main new feature in Splash 1.6 is :ref:`splash-on-request` function
which allows to process individual outgoing requests: log, abort,
change them.

Other improvements:

* a new :ref:`http-gc` endpoint which allows to clear QWebKit caches;
* Docker images are updated with more recent package versions;
* HTTP arguments validation is improved;
* serving Splash UI under HTTPS is fixed.
* documentation improvements and typo fixes.


1.5 (2015-03-03)
----------------

In this release we introduce :ref:`Splash-Jupyter <splash-jupyter>` - a
web-based IDE for Splash Lua scripts with syntax highlighting, autocompletion
and a connected live browser window. It is implemented as a kernel for
Jupyter (IPython).

Docker images for Splash 1.5 are optimized - download size is much smaller
than in previous releases.

Other changes:

* :ref:`splash:go() <splash-go>` returned incorrect result after an
  unsuccessful splash:go() call - this is fixed;
* Lua ``main`` function can now return multiple results;
* there are testing improvements and internal cleanups.


1.4 (2015-02-10)
----------------

This release provides faster and more robust screenshot rendering,
many improvements in Splash scripting engine and other improvements
like better cookie handling.

From version 1.4 Splash requires Pillow (built with PNG support) to work.

There are backwards-incompatible changes in Splash scripts:

* splash:set_viewport() is split into
  :ref:`splash:set_viewport_size() <splash-set-viewport-size>`
  and :ref:`splash:set_viewport_full() <splash-set-viewport-full>`;
* old splash:runjs() method is renamed to :ref:`splash:evaljs() <splash-evaljs>`;
* new :ref:`splash:runjs <splash-runjs>` method just runs JavaScript code
  without returning the result of the last JS statement.

To upgrade check all splash:runjs() usages: if the returned result is used
then replace splash:runjs() with splash:evaljs().

``viewport=full`` argument is deprecated; use ``render_all=1``.

New scripting features:

* it is now possible to write custom Lua plugins stored server-side;
* a restricted version of Lua ``require`` is enabled in sandbox;
* :ref:`splash:autoload() <splash-autoload>` method for setting JS to load
  on each request;
* :ref:`splash:wait_for_resume() <splash-wait-for-resume>` method for
  interacting with async JS code;
* :ref:`splash:lock_navigation() <splash-lock-navigation>` and
  :ref:`splash:unlock_navigation() <splash-unlock-navigation>` methods;
* splash:set_viewport() is split into
  :ref:`splash:set_viewport_size() <splash-set-viewport-size>`
  and :ref:`splash:set_viewport_full() <splash-set-viewport-full>`;
* :ref:`splash:get_viewport_size() <splash-get-viewport-size>` method;
* :ref:`splash:http_get() <splash-http-get>` method for sending HTTP GET
  requests without loading result to the browser;
* :ref:`splash:set_content() <splash-set-content>` method for setting
  page content from a string;
* :ref:`splash:get_cookies() <splash-get-cookies>`,
  :ref:`splash:add_cookie() <splash-add-cookie>`,
  :ref:`splash:clear_cookies() <splash-clear-cookies>`,
  :ref:`splash:delete_cookies() <splash-delete-cookies>` and
  :ref:`splash:init_cookies() <splash-init-cookies>` methods for working
  with cookies;
* :ref:`splash:set_user_agent() <splash-set-user-agent>` method for
  setting User-Agent header;
* :ref:`splash:set_custom_headers() <splash-set-custom-headers>` method for
  setting other HTTP headers;
* :ref:`splash:url() <splash-url>` method for getting current URL;
* :ref:`splash:go() <splash-go>` now accepts ``headers`` argument;
* :ref:`splash:evaljs() <splash-evaljs>` method, which is a
  splash:runjs() from Splash v1.3.1 with improved error handling
  (it raises an error in case of JavaScript exceptions);
* :ref:`splash:runjs() <splash-runjs>` method no longer returns the result
  of last computation;
* :ref:`splash:runjs() <splash-runjs>` method handles JavaScript errors
  by returning ``ok, error`` pair;
* :ref:`splash:get_perf_stats() <splash-get-perf-stats>` method for
  getting Splash resource usage.

Other improvements:

* --max-timeout option can be passed to Splash at startup to increase or
  decrease maximum allowed timeout value;
* cookies are no longer shared between requests;
* PNG rendering becomes more efficient: less CPU is spent on compression.
  The downside is that the returned PNG images become 10-15% larger;
* there is an option (``scale_method=vector``) to resize images
  while painting to avoid pixel-based resize step - it can make taking
  a screenshot much faster on image-light webpages (up to several times faster);
* when 'height' is set and image is downscaled the rendering is more efficient
  because Splash now avoids rendering unnecessary parts;
* /debug endpoint tracks more objects;
* testing setup improvements;
* application/json POST requests handle invalid JSON better;
* undocumented splash:go_and_wait() and splash:_wait_restart_on_redirects()
  methods are removed (they are moved to tests);
* Lua sandbox is cleaned up;
* long log messages from Lua are truncated in logs;
* more detailed error info is logged;
* example script in Splash UI is simplified;
* stress tests now include PNG rendering benchmark.

Bug fixes:

* default viewport size and window geometry are now set to 1024x768;
  this fixes PNG screenshots with viewport=full;
* PNG rendering is fixed for huge viewports;
* splash:go() argument validation is improved;
* timer is properly deleted when an exception is raised in an errback;
* redirects handling for baseurl requests is fixed;
* reply is deleted only once when baseurl is used.

1.3.1 (2014-12-13)
------------------

This release fixes packaging issues with Splash 1.3.

1.3 (2014-12-04)
----------------

This release introduces an experimental
:ref:`scripting support <scripting-tutorial>`.

Other changes:

* manhole is disabled by default in Debian package;
* more objects are tracked in /debug endpoint;
* "history" in render.json now includes "queryString" keys; it makes the
  output compatible with HAR entry format;
* logging improvements;
* improved timer cancellation.

1.2.1 (2014-10-16)
------------------

* Dockerfile base image is downgraded to Ubuntu 12.04 to fix random crashes;
* Debian/buildbot config is fixed to make Splash UI available when deployed
  from deb;
* Qt / PyQt / sip / WebKit / Twisted version numbers are logged at startup.

1.2 (2014-10-14)
----------------

* All Splash rendering endpoints now accept ``Content-Type: application/json``
  POST requests with JSON-encoded rendering options as an alternative to using
  GET parameters;
* ``headers`` parameter allows to set HTTP headers (including user-agent)
  for all endpoints - previously it was possible only in proxy mode;
* ``js_source`` parameter allows to execute JS in page context without
  ``application/javascript`` POST requests;
* testing suite is switched to pytest, test running can now be parallelized;
* viewport size changes are logged;
* ``/debug`` endpoint provides leak info for more classes;
* Content-Type header parsing is less strict;
* documentation improvements;
* various internal code cleanups.

1.1 (2014-10-10)
----------------

* An UI is added - it allows to quickly check Splash features.
* Splash can now return requests/responses information in HAR_ format. See
  :ref:`render.har` endpoint and :ref:`har <arg-har>` argument of render.json
  endpoint. A simpler :ref:`history <arg-history>` argument is also available.
  With HAR support it is possible to get timings for various events,
  HTTP status code of the responses, HTTP headers, redirect chains, etc.
* Processing of related resources is stopped earlier and more robustly
  in case of timeouts.
* :ref:`wait <arg-wait>` parameter changed its meaning: waiting now restarts
  after each redirect.
* Dockerfile is improved: image is updated to Ubuntu 14.04;
  logs are shown immediately; it becomes possible to pass additional
  options to Splash and customize proxy/js/filter profiles; adblock filters
  are supported in Docker; versions of Python dependencies are pinned;
  Splash is started directly (without supervisord).
* Splash now tries to start Xvfb automatically - no need for xvfb-run.
  This feature requires ``xvfbwrapper`` Python package to be installed.
* Debian package improvements: Xvfb viewport matches default Splash viewport,
  it is possible to change Splash option using SPLASH_OPTS environment variable.
* Documentation is improved: finally, there are some install instructions.
* Logging: verbosity level of several logging events are changed;
  data-uris are truncated in logs.
* Various cleanups and testing improvements.

.. _HAR: http://www.softwareishard.com/blog/har-12-spec/

1.0 (2014-07-28)
----------------

Initial release.

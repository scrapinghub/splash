Changes
=======

1.5 (2015-03-03)
----------------

In this release we introduce :ref:`Splash-Jupyter <ipython-kernel>` - a
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

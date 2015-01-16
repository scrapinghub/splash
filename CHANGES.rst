Changes
=======

dev (unreleased)
----------------

This release provides many improvements in Splash scripting engine,
as well as other improvements like better cookie handling and better
image rendering.

From version 1.4 Splash requires Pillow (built with PNG support) to work.

There are backwards-incompatible changes in Splash scripts:

* old splash:runjs() method is renamed to splash:evaljs();
* new splash:runjs() method just runs JavaScript code
  without returning the result of the last JS statement.

To upgrade check all splash:runjs() usages: if the returned result is used
then replace splash:runjs() with splash:evaljs().

New scripting features:

* it is now possible to write custom Lua plugins stored server-side;
* a restricted version of Lua ``require`` is enabled in sandbox;
* splash:autoload() method for setting JS to load on each request;
* splash:lock_navigation() and splash:unlock_navigation() methods;
* splash:http_get() method for sending HTTP GET requests without loading result
  to the browser;
* splash:set_content() method for setting page content from a string;
* splash:get_cookies(), splash:add_cookie(), splash:clear_cookies(),
  splash:delete_cookies() and splash:init_cookies() methods for working
  with cookies;
* splash:set_user_agent() method for setting User-Agent header;
* splash:set_custom_headers() method for setting other HTTP headers;
* splash:url() method for getting current URL;
* splash:go() now accepts ``headers`` argument;
* splash:evaljs() method, which is a splash:runjs() from Splash v1.3.1
  with improved error handling (it raises an error in case of JavaScript
  exceptions);
* splash:runjs() method no longer returns the result of last computation;
* splash:runjs() method handles JavaScript errors by returning ``ok, error``
  pair;
* splash:get_perf_stats() command for getting Splash resource usage.

Other improvements:

* cookies are no longer shared between requests;
* PNG rendering becomes more efficient, especially for large webpages:
  images are resized while painting to avoid pixel-based resize step;
  less CPU is spent on compression. The downside is that the returned
  PNG images become 10-15% larger;
* /debug endpoint tracks more objects;
* testing setup improvements;
* application/json POST requests handle invalid JSON better;
* undocumented splash:go_and_wait() and splash:_wait_restart_on_redirects()
  methods are removed (they are moved to tests);
* Lua sandbox is cleaned up;
* long log messages from Lua are truncated in logs;
* more detailed error info is logged;
* stress tests now include PNG rendering benchmark.

Bug fixes:

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

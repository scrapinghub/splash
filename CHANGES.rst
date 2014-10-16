Changes
=======

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

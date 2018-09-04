.. _splash-lua-api-overview:

Splash Lua API Overview
-----------------------

Splash provides a lot of methods, functions and properties; all of them are
documented in :ref:`scripting-reference`, :ref:`scripting-libs`,
:ref:`splash-element`, :ref:`splash-request`, :ref:`splash-response`
and :ref:`binary-data`. Here is a short description of the most used ones:

Script as an HTTP API endpoint
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each Splash Lua script can be seen as an HTTP API endpoint, with input
arguments and structured result value. For example, you can emulate
:ref:`render.png` endpoint using Lua script, including all its
HTTP arguments.

* :ref:`splash-args` is the way to get data to the script;
* :ref:`splash-set-result-status-code` allows to change HTTP status code
  of the result;
* :ref:`splash-set-result-content-type` allows to change Content-Type
  returned to the client;
* :ref:`splash-set-result-header` allows to add custom HTTP headers to the result;
* :ref:`binary-data` section describes how to work with non-text data in
  Splash, e.g. how to return it to the client;
* :ref:`lib-treat` library allows to customize the way data is serialized
  to JSON when returning the result.

Navigation
~~~~~~~~~~

* :ref:`splash-go` - load an URL to the browser;
* :ref:`splash-set-content` - load specified content (usually HTML)
  to the browser;
* :ref:`splash-lock-navigation` and :ref:`splash-unlock-navigation` -
  lock/unlock navigation;
* :ref:`splash-on-navigation-locked` allows to inspect requests
  discarded after navigation was locked;
* :ref:`splash-set-user-agent` allows to change User-Agent header used
  for requests;
* :ref:`splash-set-custom-headers` allows to set default HTTP headers
  Splash use.
* :ref:`splash-on-request` allows to filter out or replace requests to
  related resources; it also allows to set HTTP or SOCKS5 proxy servers
  per-request;
* :ref:`splash-on-response-headers` allows to filter out requests
  based on their headers (e.g. based on Content-Type);
* :ref:`splash-init-cookies`, :ref:`splash-add-cookie`,
  :ref:`splash-get-cookies`, :ref:`splash-clear-cookies` and
  :ref:`splash-delete-cookies` allow to manage cookies.

Delays
~~~~~~

* :ref:`splash-wait` allows to wait for a specified amount of time;
* :ref:`splash-call-later` schedules a task in future;
* :ref:`splash-wait-for-resume` allows to wait until a certain JS event
  happens;
* :ref:`splash-with-timeout` allows to limit time spent in a code block.

Extracting information from a page
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* :ref:`splash-html` returns page HTML content, after it is rendered
  by a browser;
* :ref:`splash-url` returns current URL loaded in the browser;
* :ref:`splash-evaljs` and :ref:`splash-jsfunc` allow to extract data from
  a page using JavaScript;
* :ref:`splash-select` and :ref:`splash-select-all` allow to run CSS
  selectors in a page; they return Element objects which has many
  methods useful for scraping and further processing
  (see :ref:`splash-element`)
* :ref:`splash-element-text` returns text content of a DOM element;
* :ref:`splash-element-bounds` returns bounding box of an element;
* :ref:`splash-element-styles` returns computed styles of an element;
* :ref:`splash-element-form-values` return values of a ``<form>`` element;
* many methods and attributes of DOM HTMLElement_ are supported - see
  :ref:`splash-element-dom-methods` and :ref:`splash-element-dom-attributes`.

.. _HTMLElement: https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement

Screenshots
~~~~~~~~~~~

* :ref:`splash-png`, :ref:`splash-jpeg` - take PNG or JPEG screenshot;
* :ref:`splash-set-viewport-full` - change viewport size (call it before
  :ref:`splash-png` or :ref:`splash-jpeg`) to get a screenshot of the whole
  page;
* :ref:`splash-set-viewport-size` - change size of the viewport;
* :ref:`splash-element-png` and :ref:`splash-element-jpeg` - take screenshots
  of individual DOM elements.

.. _splash-lua-api-interacting:

Interacting with a page
~~~~~~~~~~~~~~~~~~~~~~~

* :ref:`splash-runjs`, :ref:`splash-evaljs` and :ref:`splash-jsfunc`
  allow to run arbitrary JavaScript in page context;
* :ref:`splash-autoload` allows to preload JavaScript libraries
  or execute some JavaScript code at the beginning of each page render;
* :ref:`splash-mouse-click`, :ref:`splash-mouse-hover`,
  :ref:`splash-mouse-press`, :ref:`splash-mouse-release` allow to send mouse
  events to specific coordinates on a page;
* :ref:`splash-element-mouse-click` and :ref:`splash-element-mouse-hover` allow
  to send mouse events to specific DOM elements;
* :ref:`splash-send-keys` and :ref:`splash-send-text` allow to send keyboard
  events to a page;
* :ref:`splash-element-send-keys` and :ref:`splash-element-send-text` allow to
  send keyboard events to particular DOM elements;
* you can get initial ``<form>`` values using :ref:`splash-element-form-values`,
  change them in Lua code, fill the form with the updated values
  using :ref:`splash-element-fill` and submit it using
  :ref:`splash-element-submit`;
* :ref:`splash-scroll-position` allows to scroll the page;
* many methods and attributes of DOM HTMLElement_ are supported - see
  :ref:`splash-element-dom-methods` and :ref:`splash-element-dom-attributes`.

Making HTTP requests
~~~~~~~~~~~~~~~~~~~~

* :ref:`splash-http-get` - send an HTTP GET request and get a response
  without loading page to the browser;
* :ref:`splash-http-post` - send an HTTP POST request and get a response
  without loading page to the browser;

Inspecting network traffic
~~~~~~~~~~~~~~~~~~~~~~~~~~

* :ref:`splash-har` returns all requests and responses in HAR_ format;
* :ref:`splash-history` returns information about redirects and pages loaded
  to the main browser window;
* :ref:`splash-on-request` allows to capture requests issued by a webpage
  and by the script;
* :ref:`splash-on-response-headers` allows to inspect (and maybe drop)
  responses once headers arrive;
* :ref:`splash-on-response` allows to inspect raw responses received
  (including content of related resources);
* :ref:`splash-response-body-enabled` enables full response bodies in
  :ref:`splash-har` and :ref:`splash-on-response`;
* see :ref:`splash-response` and :ref:`splash-request` for more information
  about Request and Response objects.

.. _HAR: http://www.softwareishard.com/blog/har-12-spec/

Browsing Options
~~~~~~~~~~~~~~~~

* :ref:`splash-js-enabled` allows to turn JavaScript support OFF:
* :ref:`splash-private-mode-enabled` allows to turn Private Mode OFF
  (it is requird for some websites because Webkit doesn't have localStorage
  available in Private Mode);
* :ref:`splash-images-enabled` allows to turn OFF downloading of images;
* :ref:`splash-plugins-enabled` allows to enable plugins (in the default
  Docker image it enables Flash);
* :ref:`splash-resource-timeout` allows to drop slow or hanging requests
  to related resources after a timeout
* :ref:`splash-indexeddb-enabled` allows to turn IndexedDB ON
* :ref:`splash-webgl-enabled` allows to turn WebGL OFF
* :ref:`splash-html5-media-enabled` allows to turn on HTML5 media
  (e.g. playback of ``<video>`` tags).
* :ref:`splash-media-source-enabled` allows to turn off Media Source Extension
  API support

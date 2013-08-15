=======================================
Splash - A javascript rendering service
=======================================

Introduction
============

Splash is a javascript rendering service with a HTTP API. It runs on top of
twisted and QT webkit for rendering pages.

The (twisted) QT reactor is used to make the sever fully asynchronous allowing
to take advantage of webkit concurrency via QT main loop.

Requirements
============

See requirements.txt


Usage
=====

To run the server::

    python -m splash.server

Run ``python -m splash.server --help`` to see options available.

API
===

The following endpoints are supported:

render.html
-----------

Return the HTML of the javascript-rendered page.

Arguments:

url : string : required
  The url to render (required)

baseurl : string : optional
  The base url to render the page with.

  If given, base HTML content will be feched from the URL given in the url
  argument, and render using this as the base url.

timeout : float : optional
  A timeout (in seconds) for the render (defaults to 30)

wait : float : optional
  Time (in seconds) to wait for updates after page is loaded
  (defaults to 0). Increase this value if you expect pages to
  contain setInterval/setTimeout javascript calls.

Curl example::

    curl http://localhost:8050/render.html?url=http://domain.com/page-with-javascript.html&timeout=10&wait=0.5

render.png
----------

Return a image (in PNG format) of the javascript-rendered page.

Arguments:

Same as `render.html`_ plus the following ones:

width : integer : optional
  Resize the rendered image to the given width (in pixels) keeping the aspect
  ratio.

height : integer : optional
  Crop the renderd image to the given height (in pixels). Often used in
  conjunction with the width argument to generate fixed-size thumbnails.

vwidth : integer : optional
  View width. Size (in pixels) of the browser viewport to render the web page.
  Defaults to 1024.

vheight : integer : optional
  View height. Size (in pixels) of the browser viewport to render the web page.
  Defaults to 768.


Curl examples::

    # render with timeout
    curl http://localhost:8050/render.png?url=http://domain.com/page-with-javascript.html&timeout=10

    # 320x240 thumbnail
    curl http://localhost:8050/render.png?url=http://domain.com/page-with-javascript.html&width=320&height=240


render.json
-----------

Return a json-encoded dictionary with HTML, PNG and meta information
about javascript-rendered page.

Arguments:

Same as `render.png`_ plus the following ones:

html : integer : optional
    Whether to include HTML in output. Possible values are
    ``1`` (include) and ``0`` (exclude). Default is 1.

png : integer : optional
    Whether to include PNG in output. Possible values are
    ``1`` (include) and ``0`` (exclude). Default is 1.

iframes : integer : optional
    Whether to include information about child frames in output.
    Possible values are  ``1`` (include) and ``0`` (exclude).
    Default is 1.

PNG image is base64-encoded.

Curl examples::

    # full information
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html

    # HTML and meta information of page itself and all its iframes
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&png=0

    # only meta information (like page/iframes titles and urls)
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&png=0&html=0

    # render html and 320x240 thumbnail at once; do not return info about iframes
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&iframes=0&width=320&height=240


Functional Tests
================

Run with::

    nosetests


Stress tests
============

There are some stress tests that spawn its own splash server and a mock server
to run tests against.

To run the stress tests::

    python -m splash.tests.stress

Typical output::

    $ python -m splash.tests.stress
    Total requests: 1000
    Concurrency   : 50
    Log file      : /tmp/splash-stress-48H91h.log
    ........................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................
    Received/Expected (per status code or error):
      200: 500/500
      504: 200/200
      502: 300/300


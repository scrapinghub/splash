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

Return a json-encoded dictionary with information about javascript-rendered
webpage. It can include HTML, PNG and other information, based on GET
arguments passed.

Arguments:

Same as `render.png`_ plus the following ones:

html : integer : optional
    Whether to include HTML in output. Possible values are
    ``1`` (include) and ``0`` (exclude). Default is 0.

png : integer : optional
    Whether to include PNG in output. Possible values are
    ``1`` (include) and ``0`` (exclude). Default is 0.

iframes : integer : optional
    Whether to include information about child frames in output.
    Possible values are  ``1`` (include) and ``0`` (exclude).
    Default is 0.


By default, URL, requested URL, page title and frame geometry is returned::

    {
        "url": "http://crawlera.com/",
        "geometry": [0, 0, 640, 480],
        "requestedUrl": "http://crawlera.com/",
        "title": "Crawlera"
    }

Add 'html=1' to request to add HTML to the result::

    {
        "url": "http://crawlera.com/",
        "geometry": [0, 0, 640, 480],
        "requestedUrl": "http://crawlera.com/",
        "html": "<!DOCTYPE html><!--[if IE 8]>....",
        "title": "Crawlera"
    }

Add 'png=1' to request to add base64-encoded PNG screenshot to the result::

    {
        "url": "http://crawlera.com/",
        "geometry": [0, 0, 640, 480],
        "requestedUrl": "http://crawlera.com/",
        "png": "iVBORw0KGgoAAAAN...",
        "title": "Crawlera"
    }

Setting both 'html=1' and 'png=1' allows to get HTML and a screenshot
at the same time - this guarantees that the screenshot matches the HTML.

By adding "iframes=1" information about iframes could be obtained::

    {
        "geometry": [0, 0, 640, 480],
        "frameName": "",
        "title": "Scrapinghub | Autoscraping",
        "url": "http://scrapinghub.com/autoscraping.html",
        "childFrames": [
            {
                "title": "Tutorial: Scrapinghub's autoscraping tool - YouTube",
                "url": "",
                "geometry": [235, 502, 497, 310],
                "frameName": "<!--framePath //<!--frame0-->-->",
                "requestedUrl": "http://www.youtube.com/embed/lSJvVqDLOOs?version=3&rel=1&fs=1&showsearch=0&showinfo=1&iv_load_policy=1&wmode=transparent",
                "childFrames": []
            }
        ],
        "requestedUrl": "http://scrapinghub.com/autoscraping.html"
    }

Note that iframes can be nested.

Pass both 'html=1' and 'iframes=1' to get HTML for all iframes
as well as for the main page::

     {
        "geometry": [0, 0, 640, 480],
        "frameName": "",
        "html": "<!DOCTYPE html...",
        "title": "Scrapinghub | Autoscraping",
        "url": "http://scrapinghub.com/autoscraping.html",
        "childFrames": [
            {
                "title": "Tutorial: Scrapinghub's autoscraping tool - YouTube",
                "url": "",
                "html": "<!DOCTYPE html>...",
                "geometry": [235, 502, 497, 310],
                "frameName": "<!--framePath //<!--frame0-->-->",
                "requestedUrl": "http://www.youtube.com/embed/lSJvVqDLOOs?version=3&rel=1&fs=1&showsearch=0&showinfo=1&iv_load_policy=1&wmode=transparent",
                "childFrames": []
            }
        ],
        "requestedUrl": "http://scrapinghub.com/autoscraping.html"
    }

Unlike 'html=1', 'png=1' does not affect data in childFrames.


Curl examples::

    # full information
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&png=1&html=1&iframes=1

    # HTML and meta information of page itself and all its iframes
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&html=1&iframes=1

    # only meta information (like page/iframes titles and urls)
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&iframes=1

    # render html and 320x240 thumbnail at once; do not return info about iframes
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&html=1&png=1&width=320&height=240



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


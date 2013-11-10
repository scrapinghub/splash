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
  (defaults to 0). Increase this value if you expect pages to contain
  setInterval/setTimeout javascript calls, because with wait=0
  callbacks of setInterval/setTimeout won't be executed. Non-zero
  'wait' is also required for PNG rendering when viewport=full
  (see later).

proxy : string : optional
  Proxy profile name. See :ref:`Proxy Profiles`.

allowed_domains : string : optional
  Comma-separated list of allowed domain names.
  If present, Splash won't load anything neither from domains
  not in this list nor from subdomains of domains not in this list.

viewport : string : optional
  View width and height (in pixels) of the browser viewport
  to render the web page. Format is "<width>x<heigth>", e.g. 800x600.
  It also accepts 'full' as value; viewport=full means that the whole
  page (possibly very tall) will be rendered. Default value is 1024x768.

  'viewport' parameter is more important for PNG rendering;
  it is supported for all rendering endpoints because javascript
  code execution can depend on viewport size.

.. note::

    viewport=full requires non-zero 'wait' parameter. This is
    an unfortunate restriction, but it seems that this is the only
    way to make rendering work reliably with viewport=full.


Curl example::

    curl http://localhost:8050/render.html?url=http://domain.com/page-with-javascript.html&timeout=10&wait=0.5

Splash supports executing JavaScript code within the context of the page.
The JavaScript code is executed after the page finished loading (including
any delay defined by 'wait') but before the page is rendered. This allow to
use the javascript code to modify the page being rendered.

To execute JavaScript code we use a POST request with the content-type set to
'application/javascript'. The body of the request contains the code to be executed.

Curl example::

    # Render page and modify its title dynamically
    curl -X POST -H "content-type: application/javascript" \
        -d "document.title='My Title';" \
        "http://localhost:8050/render.html?url=http://domain.com"

Splash supports "javascript profiles" that allows to preload javascript files,
the javascript files defined in a profile are executed after the page is loaded
and before any javascript code defined in the request.

The preloaded files can be used in the user's POST'ed code.

To enable javascript profiles support, run splash server with the
``--js-profiles-path=<path to a folder with js profiles>`` option::

    python -m splash.server --js-profiles-path=/etc/splash/js-profiles

Then create a directory with the name of the profile and place inside it the
javascript files to load. The files are loaded in the order they appear in the
filesystem. Directory example::

    /etc/splash/js-profiles/
                        mywebsite/
                              lib1.js

Note that the javascript files must be utf-8 encoded. To apply this javascript profile 
add the parameter ``js=mywebsite`` to the request::

    curl -X POST -H "content-type: application/javascript" \
        -d "myfunc('Hello');" \
        "http://localhost:8050/render.html?js=mywebsite&url=http://domain.com"

Note that this example assumes that myfunc is a javascript function defined in lib1.js.


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

script : integer : optional
    Whether to include the result of the executed javascript final
    statement in output. Possible values are ``1`` (include) and ``0``
    (exclude). Default is 0.

console : integer : optional
    Whether to include the executed javascript console messages in output.
    Possible values are ``1`` (include) and ``0`` (exclude). Default is 0.

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

When executing JavaScript code add the parameter 'script=1' to the request
to include the code output in the result::

    {
        "url": "http://crawlera.com/",
        "geometry": [0, 0, 640, 480],
        "requestedUrl": "http://crawlera.com/",
        "title": "Crawlera",
        "script": "result of script..."
    }

The JavaScript code supports the console.log() function to log messages.
Add 'console=1' to the request to include the console output in the result::

    {
        "url": "http://crawlera.com/",
        "geometry": [0, 0, 640, 480],
        "requestedUrl": "http://crawlera.com/",
        "title": "Crawlera",
        "script": "result of script...",
        "console": ["first log message", "second log message", ...]
    }


Curl examples::

    # full information
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&png=1&html=1&iframes=1

    # HTML and meta information of page itself and all its iframes
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&html=1&iframes=1

    # only meta information (like page/iframes titles and urls)
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&iframes=1

    # render html and 320x240 thumbnail at once; do not return info about iframes
    curl http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&html=1&png=1&width=320&height=240

    # Render page and execute simple Javascript function, display the js output
    curl -X POST -H "content-type: application/javascript" \
        -d "function getAd(x){ return x; } getAd('abc');" \
        "http://localhost:8050/render.json?url=http://domain.com&script=1"

    # Render page and execute simple Javascript function, display the js output and the console output
    curl -X POST -H "content-type: application/javascript" \
        -d "function getAd(x){ return x; }; console.log('some log'); console.log('another log'); getAd('abc');" \
        "http://localhost:8050/render.json?url=http://domain.com&script=1&console=1"


Proxy Profiles
==============

Splash supports "proxy profiles" that allows to set proxy handling rules
per-request using ``proxy`` GET parameter.

To enable proxy profiles support, run splash server with
``--proxy-profiles-path=<path to a folder with proxy profiles>`` option::

    python -m splash.server --proxy-profiles-path=/etc/splash/proxy-profiles

Then create an INI file with "proxy profile" config inside the
specified folder, e.g. ``/etc/splash/proxy-profiles/mywebsite.ini``.
Example contents of this file::

    [proxy]

    ; required
    host=proxy.crawlera.com
    port=8010

    ; optional, default is no auth
    username=username
    password=password

    [rules]
    ; optional, default ".*"
    whitelist=
        .*mywebsite\.com.*

    ; optional, default is no blacklist
    blacklist=
        .*\.js.*
        .*\.css.*
        .*\.png

whitelist and blacklist are newline-separated lists of regexes.
If URL matches one of whitelist patterns and matches none of blacklist
patterns, proxy specified in ``[proxy]`` section is used;
no proxy is used otherwise.

Then, to apply proxy rules according to this profile,
add ``proxy=mywebsite`` parameter to request::

    curl http://localhost:8050/render.html?url=http://mywebsite.com/page-with-javascript.html&proxy=mywebsite

Splash as a Proxy
=================

Splash supports working as HTTP proxy. In this mode all the HTTP requests received
will be proxied and the response will be rendered based in the following HTTP headers:

X-Splash-render : string : required
  The render mode to use, valid modes are: html, png and json. These modes have
  the same behavior as the endpoints: render.html, render.png and render.json respectively.

X-Splash-js-source : string
  Allow to execute javascript code same as POST js code to render.html

X-Splash-timeout : string
  Same as 'timeout' argument for render.html

X-Splash-wait : string
  Same as 'wait' argument for render.html

X-Splash-proxy : string
  Same as 'proxy' argument for render.html

X-Splash-allowed-domains : string
  Same as 'allowed_domains' argument for render.html

X-Splash-viewport : string
  Same as 'viewport' argument for render.html

X-Splash-width : string
  Same as 'width' argument for render.png

X-Splash-height : string
  Same as 'height' argument for render.png

X-Splash-html : string
  Same as 'html' argument for render.json

X-Splash-png : string
  Same as 'png' argument for render.json

X-Splash-iframes : string
  Same as 'iframes' argument for render.json

X-Splash-script : string
  Same as 'script' argument for render.json

X-Splash-console : string
  Same as 'console' argument for render.json


Splash proxy mode is enabled by default, to disable it
run splash server with ``--disable-proxy``
option::

    python -m splash.server --disable-proxy


Curl examples::

    # Display json stats
    curl -x localhost:8051 -H "X-Splash-render: json" \
        http://www.mywebsite.com

    # Execute JS and return output
    curl -x localhost:8051 \
        -H "X-Splash-render: json" \
        -H "X-Splash-script: 1" \
        -H "X-Splash-exec-javascript: function test(x){ return x; } test('abc');" \
        http://www.mywebsite.com

    # Send POST request to site and save screenshot of results
    curl -X POST -d '{"key":"val"}' -x localhost:8051 -o screenshot.png \
        -H "X-Splash-render: png" \
        http://www.mywebsite.com


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


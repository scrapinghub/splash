=======================================
Splash - A javascript rendering service
=======================================

Introduction
============

Splash is a javascript rendering service with a HTTP API. It runs on top of
twisted and QT webkit for rendering pages.

The (twisted) QT reactor is used to make the sever fully asynchronous allowing
to take advantage of webkit concurrency via QT main loop.

.. toctree::
   :maxdepth: 2

   install

Usage
=====

To run the server::

    python -m splash.server

Run ``python -m splash.server --help`` to see options available.

API
===

By default, Splash API endpoints listen to port 8050 on all available
IPv4 addresses. To change the port use ``--port`` option::

    python -m splash.server --port=5000

The following endpoints are supported:

render.html
-----------

Return the HTML of the javascript-rendered page.

Arguments:

.. _arg-url:

url : string : required
  The url to render (required)

.. _arg-baseurl:

baseurl : string : optional
  The base url to render the page with.

  If given, base HTML content will be feched from the URL given in the url
  argument, and render using this as the base url.

.. _arg-timeout:

timeout : float : optional
  A timeout (in seconds) for the render (defaults to 30)

.. _arg-wait:

wait : float : optional
  Time (in seconds) to wait for updates after page is loaded
  (defaults to 0). Increase this value if you expect pages to contain
  setInterval/setTimeout javascript calls, because with wait=0
  callbacks of setInterval/setTimeout won't be executed. Non-zero
  'wait' is also required for PNG rendering when viewport=full
  (see later).

.. _arg-proxy:

proxy : string : optional
  Proxy profile name. See :ref:`Proxy Profiles`.

.. _arg-js:

js : string : optional
  Javascript profile name. See :ref:`Javascript Profiles`.

.. _arg-filters:

filters : string : optional
  Comma-separated list of request filter names. See `Request Filters`_

.. _arg-allowed-domains:

allowed_domains : string : optional
  Comma-separated list of allowed domain names.
  If present, Splash won't load anything neither from domains
  not in this list nor from subdomains of domains not in this list.

.. _arg-viewport:

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

.. _arg-images:

images : integer : optional
    Whether to download images. Possible values are
    ``1`` (download images) and ``0`` (don't downoad images). Default is 1.

    Note that cached images may be displayed even if this parameter is 0.
    You can also use `Request Filters`_ to strip unwanted contents based on URL.

Examples
~~~~~~~~

Curl example::

    curl 'http://localhost:8050/render.html?url=http://domain.com/page-with-javascript.html&timeout=10&wait=0.5'

The result is always encoded to utf-8. Always decode HTML data returned
by render.html endpoint from utf-8 even if there are tags like

::

   <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">

in the result.

render.png
----------

Return a image (in PNG format) of the javascript-rendered page.

Arguments:

Same as `render.html`_ plus the following ones:

.. _arg-width:

width : integer : optional
  Resize the rendered image to the given width (in pixels) keeping the aspect
  ratio.

.. _arg-height:

height : integer : optional
  Crop the renderd image to the given height (in pixels). Often used in
  conjunction with the width argument to generate fixed-size thumbnails.

Examples
~~~~~~~~

Curl examples::

    # render with timeout
    curl 'http://localhost:8050/render.png?url=http://domain.com/page-with-javascript.html&timeout=10'

    # 320x240 thumbnail
    curl 'http://localhost:8050/render.png?url=http://domain.com/page-with-javascript.html&width=320&height=240'


render.har
----------

Return information about Splash interaction with a website in HAR_ format.
It includes information about requests made, responses received, timings,
headers, cookies, etc.

You can use online `HAR viewer`_ to visualize information returned from
this endpoint; It will be very similar to "Network" tabs in Firefox and Chrome
developer tools.

Currently this endpoint doesn't expose raw request and response contents;
only meta-information like headers and timings is available.

Arguments for this endpoint are the same as for `render.html`_.

.. _HAR: http://www.softwareishard.com/blog/har-12-spec/
.. _HAR viewer: http://www.softwareishard.com/har/viewer/


render.json
-----------

Return a json-encoded dictionary with information about javascript-rendered
webpage. It can include HTML, PNG and other information, based on GET
arguments passed.

Arguments:

Same as `render.png`_ plus the following ones:

.. _arg-html:

html : integer : optional
    Whether to include HTML in output. Possible values are
    ``1`` (include) and ``0`` (exclude). Default is 0.

.. _arg-png:

png : integer : optional
    Whether to include PNG in output. Possible values are
    ``1`` (include) and ``0`` (exclude). Default is 0.

.. _arg-iframes:

iframes : integer : optional
    Whether to include information about child frames in output.
    Possible values are  ``1`` (include) and ``0`` (exclude).
    Default is 0.

.. _arg-script:

script : integer : optional
    Whether to include the result of the executed javascript final
    statement in output (see :ref:`execute javascript`).
    Possible values are ``1`` (include) and ``0`` (exclude). Default is 0.

.. _arg-console:

console : integer : optional
    Whether to include the executed javascript console messages in output.
    Possible values are ``1`` (include) and ``0`` (exclude). Default is 0.

.. _arg-history:

history : integer : optional
    Whether to include the history of requests/responses for webpage main
    frame. Possible values are ``1`` (include) and ``0`` (exclude).
    Default is 0.

    Use it to get HTTP status codes, cookies and headers.
    Only information about "main" requests/responses is returned
    (i.e. information about related resources like images and AJAX queries
    is not returned).

.. _arg-har:

har : integer : optional
    Whether to include HAR_ in output. Possible values are
    ``1`` (include) and ``0`` (exclude). Default is 0.
    If this option is ON the result will contain the same data
    as `render.har`_ provides under 'har' key.

Examples
~~~~~~~~

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

When executing JavaScript code (see :ref:`execute javascript`) add the
parameter 'script=1' to the request to include the code output in the result::

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
    curl 'http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&png=1&html=1&iframes=1'

    # HTML and meta information of page itself and all its iframes
    curl 'http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&html=1&iframes=1'

    # only meta information (like page/iframes titles and urls)
    curl 'http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&iframes=1'

    # render html and 320x240 thumbnail at once; do not return info about iframes
    curl 'http://localhost:8050/render.json?url=http://domain.com/page-with-iframes.html&html=1&png=1&width=320&height=240'

    # Render page and execute simple Javascript function, display the js output
    curl -X POST -H 'content-type: application/javascript' \
        -d 'function getAd(x){ return x; } getAd("abc");' \
        'http://localhost:8050/render.json?url=http://domain.com&script=1'

    # Render page and execute simple Javascript function, display the js output and the console output
    curl -X POST -H 'content-type: application/javascript' \
        -d 'function getAd(x){ return x; }; console.log("some log"); console.log("another log"); getAd("abc");' \
        'http://localhost:8050/render.json?url=http://domain.com&script=1&console=1'


.. _execute javascript:

Executing custom Javascript code within page context
====================================================

Splash supports executing JavaScript code within the context of the page.
The JavaScript code is executed after the page finished loading (including
any delay defined by 'wait') but before the page is rendered. This allow to
use the javascript code to modify the page being rendered.

To execute JavaScript code we use a POST request with the content-type set to
'application/javascript'. The body of the request should contain the code to
be executed.

Curl example::

    # Render page and modify its title dynamically
    curl -X POST -H 'content-type: application/javascript' \
        -d 'document.title="My Title";' \
        'http://localhost:8050/render.html?url=http://domain.com'

To get the result of a javascript function executed within page
context use `render.json`_ endpoint with script=1 parameter.

In :ref:`Splash-as-a-proxy <splash as a proxy>` mode use ``X-Splash-js-source``
header instead of a POST request.

.. _javascript profiles:

Javascript Profiles
-------------------

Splash supports "javascript profiles" that allows to preload javascript files.
Javascript files defined in a profile are executed after the page is loaded
and before any javascript code defined in the request.

The preloaded files can be used in the user's POST'ed code.

To enable javascript profiles support, run splash server with the
``--js-profiles-path=<path to a folder with js profiles>`` option::

    python -m splash.server --js-profiles-path=/etc/splash/js-profiles

Then create a directory with the name of the profile and place inside it the
javascript files to load (note they must be utf-8 encoded).
The files are loaded in the order they appear in the filesystem.
Directory example::

    /etc/splash/js-profiles/
                        mywebsite/
                              lib1.js

To apply this javascript profile add the parameter
``js=mywebsite`` to the request::

    curl -X POST -H 'content-type: application/javascript' \
        -d 'myfunc("Hello");' \
        'http://localhost:8050/render.html?js=mywebsite&url=http://domain.com'

Note that this example assumes that myfunc is a javascript function
defined in lib1.js.

Javascript Security
-------------------

If Splash is started with ``--js-cross-domain-access`` option

::

    python -m splash.server --js-cross-domain-access

then javascript code is allowed to access the content of iframes
loaded from a security origin diferent to the original page (browsers usually
disallow that). This feature is useful for scraping, e.g. to extract the
html of a iframe page. An example of its usage::

    curl -X POST -H 'content-type: application/javascript' \
        -d 'function getContents(){ var f = document.getElementById("external"); return f.contentDocument.getElementsByTagName("body")[0].innerHTML; }; getContents();' \
        'http://localhost:8050/render.html?url=http://domain.com'

The javascript function 'getContents' will look for a iframe with
the id 'external' and extract its html contents.

Note that allowing cross origin javascript calls is a potential
security issue, since it is possible that secret information (i.e cookies)
is exposed when this support is enabled; also, some websites don't load
when cross-domain security is disabled, so this feature is OFF by default.

.. _request filters:

Request Filters
===============

Splash supports filtering requests based on
`Adblock Plus <https://adblockplus.org/>`_ rules. You can use
filters from `EasyList`_ to remove ads and tracking codes
(and thus speedup page loading), and/or write filters manually to block
some of the requests (e.g. to prevent rendering of images, mp3 files,
custom fonts, etc.)

To activate request filtering support start splash with ``--filters-path``
option::

    python -m splash.server --filters-path=/etc/splash/filters

The folder ``--filters-path`` points to should contain ``.txt`` files with
filter rules in Adblock Plus format. You may download ``easylist.txt``
from EasyList_ and put it there, or create ``.txt`` files with your own rules.

For example, let's create a filter that will prevent custom fonts
in ``ttf`` and ``woff`` formats from loading (due to qt bugs they may cause
splash to segfault on Mac OS X)::

    ! put this to a /etc/splash/filters/nofonts.txt file
    ! comments start with an exclamation mark

    .ttf|
    .woff|

To use this filter in a request add ``filters=nofonts`` GET parameter
to the query::

    curl 'http://localhost:8050/render.png?url=http://domain.com/page-with-fonts.html&filters=nofonts'

You can apply several filters; separate them by comma::

    curl 'http://localhost:8050/render.png?url=http://domain.com/page-with-fonts.html&filters=nofonts,easylist'

If ``default.txt`` file is present in ``--filters-path`` folder it is
used by default when ``filters`` GET argument is not specified. Pass
``filters=none`` if you don't want default filters to be applied.

To learn about Adblock Plus filter syntax check these links:

* https://adblockplus.org/en/filter-cheatsheet
* https://adblockplus.org/en/filters

Splash doesn't support full Adblock Plus filters syntax, there are some
limitations:

* element hiding rules are not supported; filters can prevent network
  request from happening, but they can't hide parts of an already loaded page;
* only ``domain`` option is supported.

Unsupported rules are silently discarded.

.. note::

    If you want to stop downloading images check :ref:`'images' <arg-images>`
    GET parameter. It doesn't require URL-based filters to work, and it can
    filter images that are hard to detect using URL-based patterns.

.. warning::

    It is very important to have `pyre2 <https://github.com/axiak/pyre2>`_
    library installed if you are going to use filters with a large number
    of rules (this is the case for files downloaded from EasyList_).

    Without pyre2 library splash (via `adblockparser`_) relies on re module
    from stdlib, and it can be 1000x+ times slower than re2 - it may be
    faster to download files than to discard them if you have a large number
    of rules and don't use re2. With re2 matching becomes very fast.

    Make sure you are not using re2==0.2.20 installed from PyPI (it is broken);
    use the latest version from github.

.. _adblockparser: https://github.com/scrapinghub/adblockparser
.. _EasyList: https://easylist.adblockplus.org/en/


.. _proxy profiles:

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

    curl 'http://localhost:8050/render.html?url=http://mywebsite.com/page-with-javascript.html&proxy=mywebsite'

If ``default.ini`` profile is present, it will be used when ``proxy``
GET argument is not specified. If you have ``default.ini`` profile
but don't want to apply it pass ``none`` as ``proxy`` value.


.. _splash as a proxy:

Splash as a Proxy
=================

Splash supports working as HTTP proxy. In this mode all the HTTP requests
received will be proxied and the response will be rendered based in the
following HTTP headers:

X-Splash-render : string : required
  The render mode to use, valid modes are: html, png and json. These modes have
  the same behavior as the endpoints: `render.html`_, `render.png`_
  and `render.json`_ respectively.

X-Splash-js-source : string
  Allow to execute custom javascript code in page context.
  See :ref:`execute javascript`.

X-Splash-js : string
  Same as :ref:`'js' <arg-js>` argument for `render.html`_.
  See :ref:`Javascript Profiles`.

X-Splash-timeout : string
  Same as :ref:`'timeout' <arg-timeout>` argument for `render.html`_.

X-Splash-wait : string
  Same as :ref:`'wait' <arg-wait>` argument for `render.html`_.

X-Splash-proxy : string
  Same as :ref:`'proxy' <arg-proxy>` argument for `render.html`_.

X-Splash-filters : string
  Same as :ref:`'filters' <arg-filters>` argument for `render.html`_.

X-Splash-allowed-domains : string
  Same as :ref:`'allowed_domains' <arg-allowed-domains>` argument for `render.html`_.

X-Splash-viewport : string
  Same as :ref:`'viewport' <arg-viewport>` argument for `render.html`_.

X-Splash-images : string
  Same as :ref:`'images' <arg-images>` argument for `render.html`_.

X-Splash-width : string
  Same as :ref:`'width' <arg-width>` argument for `render.png`_.

X-Splash-height : string
  Same as :ref:`'height' <arg-height>` argument for `render.png`_.

X-Splash-html : string
  Same as :ref:`'html' <arg-html>` argument for `render.json`_.

X-Splash-png : string
  Same as :ref:`'png' <arg-png>` argument for `render.json`_.

X-Splash-iframes : string
  Same as :ref:`'iframes' <arg-iframes>` argument for `render.json`_.

X-Splash-script : string
  Same as :ref:`'script' <arg-script>` argument for `render.json`_.

X-Splash-console : string
  Same as :ref:`'console' <arg-console>` argument for `render.json`_.

X-Splash-history : string
  Same as :ref:`'history' <arg-history>` argument for `render.json`_.

X-Splash-har : string
  Same as :ref:`'har' <arg-har>` argument for `render.json`_.

Curl examples::

    # Display json stats
    curl -x localhost:8051 -H 'X-Splash-render: json' \
        http://www.domain.com

    # Get the html page and screenshot
    curl -x localhost:8051 \
        -H "X-Splash-render: json" \
        -H "X-Splash-html: 1" \
        -H "X-Splash-png: 1" \
        http://www.mywebsite.com

    # Execute JS and return output
    curl -x localhost:8051 \
        -H 'X-Splash-render: json' \
        -H 'X-Splash-script: 1' \
        -H 'X-Splash-js-source: function test(x){ return x; } test("abc");' \
        http://www.domain.com

    # Send POST request to site and save screenshot of results
    curl -X POST -d '{"key":"val"}' -x localhost:8051 -o screenshot.png \
        -H 'X-Splash-render: png' \
        http://www.domain.com

Splash proxy mode is enabled by default; it uses port 8051. To change the port
use ``--proxy-portnum`` option::

    python -m splash.server --proxy-portnum=8888

To disable Splash proxy mode run splash server with ``--disable-proxy`` option::

    python -m splash.server --disable-proxy


Functional Tests
================

.. image:: https://secure.travis-ci.org/scrapinghub/splash.png?branch=master
   :target: http://travis-ci.org/scrapinghub/splash

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

.. include:: ../CHANGES.rst

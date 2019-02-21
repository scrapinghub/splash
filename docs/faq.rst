FAQ
===

.. _using-http-api:

How to send requests to Splash HTTP API?
----------------------------------------

The recommended way is to use ``application/json`` POST requests,
because this way you can preserve data types, and there is no limit on
request size.

Python, using ``requests`` library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

requests_ library is a popular way to send HTTP requests in Python.
It provides a shortcut for sending JSON POST requests. Let's send
a simple Lua script to :ref:`run` endpoint:

.. code-block:: python

    import requests

    script = """
    splash:go(args.url)
    return splash:png()
    """
    resp = requests.post('http://localhost:8050/run', json={
        'lua_source': script,
        'url': 'http://example.com'
    })
    png_data = resp.content

.. _requests: http://docs.python-requests.org/en/master/

Python + Scrapy
~~~~~~~~~~~~~~~

Scrapy_ is a popular web crawling and scraping framework.
For Scrapy_ + Splash integration use scrapy-splash_ library.

.. _Scrapy: https://scrapy.org/
.. _scrapy-splash: https://github.com/scrapy-plugins/scrapy-splash

R language
~~~~~~~~~~

There is a third-party library which makes it easy to use Splash
in R language: https://github.com/hrbrmstr/splashr

curl
~~~~

::

    curl --header "Content-Type: application/json" \
         -X POST \
         --data '{"url":"http://example.com","wait":1.0}' \
         'http://localhost:8050/render.html'

httpie
~~~~~~

httpie_ is a command-line utility for sending HTTP requests; it has a nice
API for sending for JSON POST requests::

    http POST localhost:8050/render.png url=http://example.com width=200 > img.png

.. _httpie: https://httpie.org

HTML
~~~~

You can embed Splash results directly in HTML pages. This is not the best,
as you'll be rendering the website each time this HTML page is opened.
But still, you can do this:

.. code-block:: html

    <img src="http://splash-url:8050/render.jpeg?url=http://example.com&width=300"/>


.. _timeouts:

I'm getting lots of 504 Timeout errors, please help!
----------------------------------------------------

HTTP 504 error means a request to Splash took more than
:ref:`timeout <arg-timeout>` seconds to complete (30s by default) - Splash
aborts script execution after the timeout. To override the timeout value
pass :ref:`'timeout' <arg-timeout>` argument to the Splash endpoint
you're using.

Note that the maximum allowed ``timeout`` value is limited by the maximum
timeout setting, which is by default 60 seconds. In other words,
by default you can't pass ``?timeout=300`` to run a long script - an
error will be returned.

Maximum allowed timeout can be increased by passing ``--max-timeout``
option to Splash server on startup (see :ref:`docker-custom-options`)::

    $ docker run -it -p 8050:8050 scrapinghub/splash --max-timeout 3600

If you've installed Splash without Docker, use
::

    $ python3 -m splash.server --max-timeout 3600

The next question is why a request can need 10 minutes to render.
There are 3 common reasons:

.. _504-slow-website:

1. Slow website
~~~~~~~~~~~~~~~

A website can be really slow, or it can try to get some remote
resources which are really slow.

There is no way around increasing timeouts and reducing request rate
if the website itself is slow. However, often the problem lays in unreliable
remote resources like third-party trackers or advertisments. By default
Splash waits for all remote resources to load, but in most cases it is
better not to wait for them forever.

To abort resource loading after a timeout and give the whole page a chance to
render use resource timeouts. For render.*** endpoints use
:ref:`'resource_timeout' <arg-resource-timeout>` argument;
for :ref:`execute` or :ref:`run` use either :ref:`splash-resource-timeout` or
``request:set_timeout`` (see :ref:`splash-on-request`).

It is a good practive to always set resource_timeout; something similar to
``resource_timeout=20`` often works well.

.. _504-slow-script:

2. Splash Lua script does too many things
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a script fetches many pages or uses large delays then timeouts
are inevitable. Sometimes you have to run such scripts; in this case increase
``--max-timeout`` Splash option and use larger :ref:`timeout <arg-timeout>`
values.

But before increasing the timeouts consider splitting your script
into smaller steps and sending them to Splash individually.
For example, if you need to fetch 100 websites, don't write a Splash Lua
script which takes a list of 100 URLs and fetches them - write a Splash Lua
script that takes 1 URL and fetches it, and send 100 requests to Splash.
This approach has a number of benefits: it makes scripts more simple and
robust and enables parallel processing.


.. _504-splash-overloaded:

3. Splash instance is overloaded
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When Splash is overloaded it may start producing 504 errors.

Splash renders requests in parallel, but it doesn't render them *all*
at the same time - concurrency is limited to a value set at startup
using ``--slots`` option. When all slots are used a request is put into
a queue. The thing is that a timeout starts to tick once Splash receives
a request, not when Splash starts to render it. If a request stays in an
internal queue for a long time it can timeout even if a website is fast
and splash is capable of rendering the website.

To increase rendering speed and fix an issue with a queue it is recommended
to start several Splash instances and use a load balancer capable of
maintaining its own request queue. HAProxy_ has all necessary features;
check an example config
`here <https://github.com/scrapinghub/splash/blob/master/splash/examples/splash-haproxy.conf>`__.
A shared request queue in a load balancer also helps with reliability:
you won't be loosing requests if a Splash instance needs to be restarted.

.. note::

    Nginx_ (which is another popular load balancer) provides an
    internal queue only in its commercial version, `Nginx Plus`_.


.. _HAProxy: http://www.haproxy.org/
.. _Nginx Plus: https://www.nginx.com/products/
.. _Nginx: https://www.nginx.com/

.. _splash-in-production:

How to run Splash in production?
--------------------------------

Easy Way
~~~~~~~~

If you want to get started quickly take a look at Aquarium_
(which is a Splash setup without many of the pitfalls) or use
a hosted solution like `ScrapingHub's <http://scrapinghub.com/splash/>`__.

Don't forget to use resource timeous in your client code (see
:ref:`504-slow-website`). It also makes sense to retry a couple of times
if Splash returns 5xx error response.

.. _Aquarium: https://github.com/TeamHG-Memex/aquarium

Hard Way
~~~~~~~~

If you want to create your own production setup, here is a small
non-exhaustive checklist:

* Splash should be daemonized and started on boot;
* in case of failures or segfaults Splash must be restarted;
* memory usage should be limited;
* several Splash instances should be started to use all CPU cores and/or
  multiple servers;
* requests queue should be moved to the load balancer to make rendering more
  robust (see :ref:`504-splash-overloaded`).

Of course, it is also good to setup monitoring, configuration management,
etc. - all the usual stuff.

To daemonize Splash, start it on boot and restart on failures
one can use Docker: since Docker 1.2 there are ``--restart``
and ``-d`` options which can be used together. Another way to do that is
to use standard tools like upstart, systemd
or supervisor.

.. note::

    Docker ``--restart`` option won't work without ``-d``.

Splash uses an unbound in-memory cache and so it will eventually consume
all RAM. A workaround is to restart the process when it uses too much memory;
there is Splash ``--maxrss`` option for that. You can also add Docker
``--memory`` option to the mix.

In production it is a good idea to pin Splash version - instead of
``scrapinghub/splash`` it is usually better to use something like
``scrapinghub/splash:2.0``.

A command for starting a long-running Splash server which uses
up to 4GB RAM and daemonizes & restarts itself could look like this::

    $ docker run -d -p 8050:8050 --memory=4.5G --restart=always scrapinghub/splash:3.1 --maxrss 4000

You also need a load balancer; for example configs check Aquarium_ or
an HAProxy config in Splash `repository <https://github.com/scrapinghub/splash/blob/master/examples/splash-haproxy.conf>`__.

Ansible Way
~~~~~~~~~~~

Ansible_ role for Splash is available via third-party project:
https://github.com/nabilm/ansible-splash.

.. _Ansible: https://www.ansible.com/

.. _rendering-problems:


Website is not rendered correctly
---------------------------------

Sometimes websites are not rendered correctly by Splash. Common reasons:

* not enough wait time; solution - wait more (see e.g. :ref:`splash-wait`);
* non-working localStorage in Private Mode. This is a common issue e.g. for
  websites based on AngularJS. If rendering doesn't work, try disabling
  Private mode (see :ref:`disable-private-mode`).
* Sometimes content is lazy-loaded, or loaded only in a response for user
  actions (e.g. page scrolling). Try increasing viewport size to make
  everything visible, and waiting a bit after that
  (see :ref:`splash-set-viewport-full`). You may also have to simulate
  mouse and keyboard events (see :ref:`splash-lua-api-interacting`).
* Missing features in WebKit used by Splash. Splash now uses
  https://github.com/annulen/webkit, which is much more recent than WebKit
  provided by Qt; we'll be updating Splash WebKit as annulen's webkit
  develops.
* Website may show a different content based on User-Agent header or based
  on IP address. Use :ref:`splash-set-user-agent` to change the default
  User-Agent header. If you're running Splash in a cloud and not getting good
  results, try reproducing it locally as well, just in case results depend on
  IP address.
* Website requires Flash. You can enable it using
  :ref:`splash-plugins-enabled`.
* Website requires IndexedDB_. Enable it using :ref:`splash-indexeddb-enabled`.
* If there is no video or other media, use :ref:`html5_media <arg-html5-media>`
  Splash HTTP argument or :ref:`splash-html5-media-enabled` property to enable
  HTML5 media, or :ref:`splash-plugins-enabled` to enable Flash.
* Website has compatibility issues with Webkit version Splash is using.
  A quick (though not precise) way to check it is to try opening a page
  in Safari.

.. _IndexedDB: https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API

Splash crashes
--------------

Common reasons:

* Qt or WebKit bugs which cause Splash to hang or crash. Unfortunately,
  they can be hard to fix in Splash, as Splash is relying on these projects.
  That said, often the whole website works, but some specific .js (or other)
  file causes problems. In this case you can try these steps:
  
  * Run Splash locally with v2 verbosity, e.g.
    ``docker run -it -p8050:8050 scrapinghub/splash -v2``
  * Go to ``http://0.0.0.0:8050`` and paste your url (with the default Lua
    script), or try to reproduce the issue otherwise, using this Splash
    instance.
  * If Splash instance failed and stopped (you reproduced the issue),
    check the log in terminal. Pay special attention to network activity.
    For example, if the last response was for an url like
    ``https://example.com/static/myscript123.min.js`` with JS, we may suspect
    that this particular JavaScript file contains some code which makes
    Splash crash.
  * Filter out this .js file using :ref:`splash-on-request`:
  
    .. code-block:: lua

        function main(splash, args)
            splash:on_request(function(request)
                if request.url:find('myscript123') ~= nil then
                    request:abort()
                end
            end)
            assert(splash:go(args.url))
            assert(splash:wait(0.5))
            return {
                html = splash:html(),
                png = splash:png(),
                har = splash:har(),
            }
        end

    Alternatively, use :ref:`request filters` to filter it out.

* Some of the crashes can be solved by disabling HTML 5 media
  (:ref:`splash-html5-media-enabled` property or
  :ref:`html5_media <arg-html5-media>` HTTP API argument) - note it is
  disabled by default.

* Sometimes Splash may crash, and you get a Python traceback in the log.
  In this case it is likely to be a Splash bug which can be fixed in Splash.
  Please report it at https://github.com/scrapinghub/splash/issues, pasting
  the whole traceback and parameters of the request you're making, if possible
  (URL, endpoint or Lua script used).

If you have troubles making Splash work, consider asking a question
at https://stackoverflow.com. If you think it is a Splash bug,
raise an issue at https://github.com/scrapinghub/splash/issues.

.. _disable-private-mode:

How do I disable Private mode?
------------------------------

With Splash>=2.0, you can disable Private mode (which is "on" by default).
There are two ways to go about it:

- at startup, with the ``--disable-private-mode`` argument, e.g., if you're
  using Docker::

        $ sudo docker run -it -p 8050:8050 scrapinghub/splash --disable-private-mode

- at runtime when using the ``/execute`` endpoint and setting
  :ref:`splash-private-mode-enabled` attribute to ``false``

Note that if you disable private mode then browsing data may persist
between requests (cookies are not affected though). If you're using
Splash in a shared environment it could mean some information about
requests you're making can be accessible for other Splash users.

You may still want to turn Private mode off because in WebKit localStorage
doesn't work when Private mode is enabled, and it is not possible
to provide a JavaScript shim for localStorage. So for some websites
(AngularJS websites are common offenders) you may have to turn
Private model off.

.. _why-splash:

Why was Splash created in the first place?
------------------------------------------

Please refer to `this great answer from kmike on reddit.
<https://www.reddit.com/r/Python/comments/2xp5mr/handling_javascript_in_scrapy_with_splash/cp2vgd6>`__

.. _why-css-images:

Why are CSS styling and images missing from the .har archive?
-------------------------------------------------------------

Webkit has an in-memory cache (also called `page-cache <https://webkit.org/blog/427/webkit-page-cache-i-the-basics/>`_)
and a `network cache <http://doc.qt.io/qt-5/qnetworkrequest.html#CacheLoadControl-enum>`_.

If you tell splash to load two pages that share some common resources,
the second page's .har file will not contain the shared resources because
they were cached through the page cache.

If you want the .har file to contain all the resources for that page,
run splash with the command-line option ``--disable-browser-caches``.

.. _why-lua:

Why does Splash use Lua for scripting, not Python or JavaScript?
----------------------------------------------------------------

Check this `GitHub Issue <https://github.com/scrapinghub/splash/issues/117>`__
for the motivation.

.. _render-html-doesnt-work:

:ref:`render.html` result looks broken in a browser
---------------------------------------------------

When you check ``http://<splash-server>:8050/render.html?url=<url>``
in a browser it is likely stylesheets & other resources won't
load properly. It happens when resource URLs are relative - the browser
will resolve them as relative to
``http://<splash-server>:8050/render.html?url=<url>``, not to ``url``.
This is not a Splash bug, it is a standard browser behaviour.

If you just want to check how the page looks like after rendering
use :ref:`render.png` or :ref:`render.jpeg` endpoints.
If screenshot is not an option and you want to display html with images,
etc. using a browser then you may post-process the HTML and add
an appropriate `\<base\>`_ HTML tag to the page.

.. _<base>: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/base

:ref:`baseurl <arg-baseurl>` Splash argument can't help here. It allows
to render a page located at one URL as if it is located at another
URL. For example, you can host a copy of page HTML on your server,
but use baseurl of the original page. This way Splash will resolve
relative URLs as relative to original page URL, so that you can get
e.g. a proper screenshot or execute proper JavaScript code.

But by passing baseurl you're instructing **Splash** to use it,
not **your browser**. It doesn't change relative links to absolute in DOM,
it makes Splash to treat them as relative to baseurl when rendering.

Changing links to absolute in DOM tree is not what browsers do when
base url is applied - e.g. if you check href attribute using JS code
it will still contain relative value even if ``<base>`` tag is used.
:ref:`render.html` returns DOM snapshot, so the links are not changed.

When you load :ref:`render.html` result in a browser it is **your browser**
who resolves relative links, not Splash, so they are resolved incorrectly.

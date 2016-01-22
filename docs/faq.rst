FAQ
===

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
option to Splash server on startup::

    $ python -m splash.server --max-timeout 3600

For Docker the command would be something like this
(see :ref:`docker-custom-options`)::

    $ docker run -it -p 8050:8050 scrapinghub/splash --max-timeout 3600

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
for :ref:`execute` use either :ref:`splash-resource-timeout` or
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

    $ docker run -d -p 8050:8050 --memory=4.5G --restart=always scrapinghub/splash:2.0 --maxrss 4000

You also need a load balancer; for example configs check Aquarium_ or
an HAProxy config in Splash `repository <https://github.com/scrapinghub/splash/blob/master/examples/splash-haproxy.conf>`__.

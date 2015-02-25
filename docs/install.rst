.. _install-docs:

Installation
============

Linux + Docker
--------------

1. Install Docker_.
2. Pull the image::

       $ sudo docker pull scrapinghub/splash

3. Start the container::

       $ sudo docker run -p 5023:5023 -p 8050:8050 -p 8051:8051 scrapinghub/splash

4. Splash is now available at 0.0.0.0 at ports
   8050 (http), 8051 (https) and 5023 (telnet).

OS X + Docker
-------------

1. Install Docker_ (via Boot2Docker_).
2. Pull the image::

       $ docker pull scrapinghub/splash

3. Start the container::

       $ docker run -p 5023:5023 -p 8050:8050 -p 8051:8051 scrapinghub/splash

4. Figure out the ip address of boot2docker::

       $ boot2docker ip

       The VM's Host only interface IP address is: 192.168.59.103

5. Splash is available at the returned IP address at ports
   8050 (http), 8051 (https) and 5023 (telnet).

.. _Docker: http://docker.io
.. _Boot2Docker: http://boot2docker.io/


.. _manual-install-ubuntu:

Ubuntu 12.04 (manual way)
-------------------------

1. Install system dependencies::

       $ sudo add-apt-repository -y ppa:pi-rho/security
       $ sudo apt-get update
       $ sudo apt-get install libre2-dev
       $ sudo apt-get install netbase ca-certificates python \
                              python-dev build-essential libicu48 \
                              xvfb libqt4-webkit python-twisted python-qt4

2. TODO: install Python dependencies using pip, clone repo, chdir to it,
   start splash.


To run the server execute the following command::

    python -m splash.server

Run ``python -m splash.server --help`` to see options available.

By default, Splash API endpoints listen to port 8050 on all available
IPv4 addresses. To change the port use ``--port`` option::

    python -m splash.server --port=5000

Requirements
~~~~~~~~~~~~

.. literalinclude:: ../requirements.txt

.. _splash and docker:

Splash Versions
---------------

``docker pull scrapinghub/splash`` will give you the latest stable Splash
release. To obtain the latest development version use
``docker pull scrapinghub/splash:master``. Specific Splash versions
are also available, e.g. ``docker pull scrapinghub/splash:1.2.1``.

Customizing Dockerized Splash
-----------------------------

.. _docker-custom-options:

Passing Custom Options
~~~~~~~~~~~~~~~~~~~~~~

To run Splash with custom options pass them to ``docker run``.
For example, let's increase log verbosity::

   $ docker run -p 8050:8050 scrapinghub/splash -v3

To see all possible options pass ``--help``. Not all options will work the
same inside Docker: changing ports doesn't make sense (use docker run options
instead), and paths are paths in the container.

.. _docker-folder-sharing:

Folders Sharing
~~~~~~~~~~~~~~~

To set custom :ref:`request filters` use -v Docker option. First, create
a folder with request filters on your local filesystem, then make it available
to the container::

   $ docker run -p 8050:8050 -v <my-filters-dir>:/etc/splash/filters scrapinghub/splash

Replace ``<my-filters-dir>`` with a path of your local folder with request
filters.

Docker Data Volume Containers can also be used. Check
https://docs.docker.com/userguide/dockervolumes/ for more info.

:ref:`proxy profiles` and :ref:`javascript profiles` can be added
in a similar way::

   $ docker run -p 8050:8050 \
         -v <my-proxy-profiles-dir>:/etc/splash/proxy-profiles \
         -v <my-js-profiles-dir>:/etc/splash/js-profiles \
         scrapinghub/splash

To setup :ref:`custom-lua-modules` mount a folder to
``/etc/splash/lua_modules``. If you use a :ref:`Lua sandbox <lua-sandbox>`
(default) don't forget to list safe modules using
``--lua-sandbox-allowed-modules`` option::

   $ docker run -p 8050:8050 \
         -v <my-lua-modules-dir>:/etc/splash/lua_modules \
         --lua-sandbox-allowed-modules 'module1;module2' \
         scrapinghub/splash

.. warning::

    Folder sharing (``-v`` option) doesn't work on OS X and Windows
    (see https://github.com/docker/docker/issues/4023).
    It should be fixed in future Docker & Boot2Docker releases.
    For now use one of the workarounds mentioned in issue comments
    or clone Splash repo and customize its Dockerfile.

Splash in Production
~~~~~~~~~~~~~~~~~~~~

In production you may want to daemonize Splash, start it on boot and restart
on failures. Since Docker 1.2 an easy way to do this is to use ``--restart``
and ``-d`` options together; another way to do that is to use standard tools
like upstart, systemd or supervisor.

.. note::

    ``--restart`` option won't work without ``-d``.

Please also take into account the memory usage: Splash uses an unbound
in-memory cache and so it will eventually consume all RAM. A workaround is
to restart the process when it uses too much memory; there is Splash
``--maxrss`` option for that. You can also add Docker ``--memory`` option
to the mix.

In production it is a good idea to pin Splash version - instead of
``scrapinghub/splash`` it is usually better to use something like
``scrapinghub/splash:1.4``.

The final command for starting a long-running Splash server which uses
up to 4GB RAM and daemonizes & restarts itself could look like this::

    $ docker run -d -p 8050:8050 --memory=4.5G --restart=always scrapinghub/splash:1.4 --maxrss 4000

.. _install-docs:

Installation
============

Linux + Docker
--------------

1. Install Docker_. Make sure Docker version >= 17 is installed.
2. Pull the image::

       $ sudo docker pull scrapinghub/splash

3. Start the container::

       $ sudo docker run -it -p 8050:8050 --rm scrapinghub/splash

4. Splash is now available at 0.0.0.0 at port 8050 (http).

OS X + Docker
-------------

1. Install Docker_ for Mac (see https://docs.docker.com/docker-for-mac/).
   Make sure Docker version >= 17 is installed.
2. Pull the image::

       $ docker pull scrapinghub/splash

3. Start the container::

       $ docker run -it -p 8050:8050 --rm scrapinghub/splash

5. Splash is available at 0.0.0.0 address at port 8050 (http).

.. _Docker: http://docker.io

.. _splash and docker:

Splash Versions
---------------

``docker pull scrapinghub/splash`` will give you the latest stable Splash
release. To obtain the latest development version use
``docker pull scrapinghub/splash:master``. Specific Splash versions
are also available, e.g. ``docker pull scrapinghub/splash:2.3.3``.

Customizing Dockerized Splash
-----------------------------

.. _docker-custom-options:

Passing Custom Options
~~~~~~~~~~~~~~~~~~~~~~

To run Splash with custom options pass them to ``docker run``, after
the image name. For example, let's increase log verbosity::

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
         scrapinghub/splash \
         --lua-sandbox-allowed-modules 'module1;module2'


.. warning::

    Folder sharing (``-v`` option) may still have issues on OS X and Windows
    (see https://github.com/docker/docker/issues/4023).
    If you have problems with volumes, use workarounds mentioned
    in issue comments or clone Splash repo and customize its Dockerfile.

Building Local Docker Images
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To build your own Docker image, checkout Splash `source code`_ using git,
then execute the following command from Splash source root::

    $ docker build -t my-local-splash .

To build :ref:`Splash-Jupyter <splash-jupyter>` Docker image use this command::

    $ docker build -t my-local-splash-jupyter -f  dockerfiles/splash-jupyter/Dockerfile .

You may have to change FROM line in :file:`dockerfiles/splash-jupyter/Dockerfile`
if you want it to be based on your local Splash Docker container.

.. _source code: https://github.com/scrapinghub/splash

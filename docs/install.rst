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

1. Install Docker_ (via the Toolbox Instructions_).
2. Create, run & load the configuration for the docker-machine

       $ docker-machine create default

       $ docker-machine start default

       $ eval "$(docker-machine env default)"

2. Pull the image::

       $ docker pull scrapinghub/splash

3. Start the container::

       $ docker run -p 5023:5023 -p 8050:8050 -p 8051:8051 scrapinghub/splash

4. Figure out the ip address of the docker-machine::

       $ docker-machine ip default

       192.168.59.103

5. Splash is available at the returned IP address at ports
   8050 (http), 8051 (https) and 5023 (telnet).

.. _Docker: http://docker.io
.. _Instructions: https://docs.docker.com/mac/


.. _manual-install-ubuntu:

Ubuntu 14.04 (manual way)
-------------------------

1. Install system dependencies (check
`provision.sh <https://github.com/scrapinghub/splash/blob/master/dockerfiles/splash/provision.sh>`)

2. Clone the repo from GitHub::

        $ git clone https://github.com/scrapinghub/splash/

3. Install dependencies with pip::

        $ cd splash
        $ pip3 install -r requirements.txt

To run the server execute the following command::

    python3 -m splash.server

Run ``python -m splash.server --help`` to see options available.

By default, Splash API endpoints listen to port 8050 on all available
IPv4 addresses. To change the port use ``--port`` option::

    python3 -m splash.server --port=5000

Required Python packages
~~~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../requirements.txt

.. _splash and docker:

Splash Versions
---------------

``docker pull scrapinghub/splash`` will give you the latest stable Splash
release. To obtain the latest development version use
``docker pull scrapinghub/splash:master``. Specific Splash versions
are also available, e.g. ``docker pull scrapinghub/splash:1.8``.

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



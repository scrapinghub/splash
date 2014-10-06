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


.. _splash and docker:

Customizing Dockerized Splash
-----------------------------

To run Splash with custom options pass them to ``docker run``.
For example, let's increase log verbosity::

   $ docker run -p 8050:8050 scrapinghub/splash -v3

To see all possible options pass ``--help``. Not all options will work the
same inside Docker: changing ports doesn't make sense (use docker run options
instead), and paths are paths in the container.

To set custom :ref:`request filters` use -v Docker option. First, create
a folder with request filters on your local filesystem, then make it available
to the container::

   $ docker run -p 8050:8050 -v <filters-dir>:/etc/splash/filters scrapinghub/splash

Docker Data Volume Containers can also be used. Check
https://docs.docker.com/userguide/dockervolumes/ for more info.

:ref:`proxy profiles` and :ref:`javascript profiles` can be added the same way::

   $ docker run -p 8050:8050 \
         -v <proxy-profiles-dir>:/etc/splash/proxy-profiles \
         -v <js-profiles-dir>:/etc/splash/js-profiles \
         scrapinghub/splash

.. warning::

    Folder sharing doesn't work on OS X
    (see https://github.com/docker/docker/issues/4023), so ``-v`` option
    won't work os OS X. It should be fixed in future Docker & Boot2Docker
    releases. For now use one of the workarounds mentioned in issue comments
    or clone Splash repo and customize its Dockerfile.


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

Requirements
============

.. literalinclude:: ../requirements.txt


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


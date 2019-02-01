Contributing to Splash
======================

Splash is free & open source.
Development happens at GitHub: https://github.com/scrapinghub/splash

Testing Suite
-------------

.. image:: https://secure.travis-ci.org/scrapinghub/splash.png?branch=master
   :target: http://travis-ci.org/scrapinghub/splash

The recommended way to execute Splash testing suite is to use a special
testing Docker container.

1. First, create a base Splash image named "splash". If you're not
   customizing Splash dependencies, and your changes are based on Splash
   master branch, you can use ``scrapinghub/splash:master`` image::

       docker pull scrapinghub/splash:master
       docker tag scrapinghub/splash:master splash

   If you've changed Splash dependencies (Python-level or system-level)
   then you have to build Splash image from scratch. Run the following
   command from the source checkout::

      docker build -t splash .

   It can take a while (maybe half an hour).
   Alternatively, you can temporarily change ``dockerfiles/tests/Dockerfile``
   or ``setup.py`` to install new dependencies.

2. Create a testing Docker image::

      docker build -t splash-tests -f dockerfiles/tests/Dockerfile .

   Testing Docker image is based on ``splash`` docker image, so you need to
   have an image called ``splash`` - we created such image at step (1).

3. Run tests inside this testing image::

      docker run -it splash-tests

   You can also pass pytest command-line arguments in the command above.
   For example, you can select only a subset of tests to execute
   (SandboxTest test case in this example)::

      docker run -it splash-tests -k SandboxTest

If you've changed Splash source code and want to re-run tests, repeat steps
(2) and (3). Step (2) should take much less time now.
Repeating step (1) is only necessary if you're adding new
dependencies to Splash (Python or system-level), or if you want to update
the base Splash image (e.g. after a recent rebase on Splash master).

There is a script in the root of Splash repository
(``runtests-docker.sh``) which combines steps (2) and (3); you can use it
during development to run tests: change Splash source code or testing source
code, then run ``./runtests-docker.sh`` from source checkout.

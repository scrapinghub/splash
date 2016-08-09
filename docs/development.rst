Splash Development
==================

Contributing
------------

Splash is free & open source.
Development happens at GitHub: https://github.com/scrapinghub/splash

Development Setup
-----------------

Consult with :ref:`install-docs` to get Splash up and running.

Install development specific dependencies with::

    $ sudo apt-get install libffi-dev libssl-dev

    pip install -r requirements-dev.txt

Functional Tests
----------------

.. image:: https://secure.travis-ci.org/scrapinghub/splash.png?branch=master
   :target: http://travis-ci.org/scrapinghub/splash

Run with::

    py.test --doctest-modules splash

To speedup test running install ``pytest-xdist`` Python package and run
Splash tests in parallel::

    py.test --doctest-modules -n4 splash

Stress tests
------------

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


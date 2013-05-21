========================================
Splash2 - A javascript rendering service
========================================

Introduction
============

Splash2 is a javascript rendering service with a HTTP API. It runs on top of
twisted and QT webkit for rendering pages.

The (twisted) QT reactor is used to make the sever fully asynchronous allowing
to take advantage of webkit concurrency via QT main loop.

Requirements
============

See requirements.txt


Usage
=====

To run the server::

    python -m splash2.server


API
===

The following endpoints are supported:

render.html
-----------

Arguments:

url : string : required
  The url to render (required)

baseurl : string : optional
  The base url to render the page with.

  If given, base HTML content will be feched from the URL given in the url
  argument, and render using this as the base url.

timeout : float : optional
  A timeout (in seconds) for the render (defaults to 30)

Returns:

The HTML of the javascript rendered page.

Curl example::

    curl http://localhost:8050/render.html?url=http://domain.com/page-with-javascript.html&timeout=10

Functional Tests
================

Run with::

    nosetests


Stess tests
===========

There are some stress tests that spawn its own splash2 server and a mock server
to run tests against.

To run the stress tests::

    python -m splash2.stress

Typical output::

    $ python -m splash2.tests.stress 
    Total requests: 1000
    Concurrency   : 50
    Log file      : /tmp/splash-stress-48H91h.log
    ........................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................
    Received/Expected (per status code or error):
      200: 500/500
      504: 200/200
      502: 300/300


=======================================
Splash - A javascript rendering service
=======================================

Introduction
============

Splash is a javascript rendering service with a HTTP API. It runs on top of
twisted and QT webkit for rendering pages.

The (twisted) QT reactor is used to make the sever fully asynchronous allowing
to take advantage of webkit concurrency via QT main loop.

See documentation in ``docs/index.rst``

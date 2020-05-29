=======================================
Splash - A javascript rendering service
=======================================

.. image:: https://img.shields.io/travis/scrapinghub/splash/master.svg
   :alt: Build Status
   :target: https://travis-ci.org/scrapinghub/splash

.. image:: https://img.shields.io/codecov/c/github/scrapinghub/splash/master.svg
   :alt: Coverage report
   :target: http://codecov.io/github/scrapinghub/splash?branch=master

.. image:: https://img.shields.io/badge/GITTER-join%20chat-green.svg
   :alt: Join the chat at https://gitter.im/scrapinghub/splash
   :target: https://gitter.im/scrapinghub/splash

Splash is a javascript rendering service with an HTTP API. It's a lightweight
browser with an HTTP API, implemented in Python 3 using Twisted and QT5.

It's fast, lightweight and state-less which makes it easy to distribute.

Documentation
-------------

Documentation is available here:
https://splash.readthedocs.io/

Using Splash with Scrapy
------------------------

To use Splash with Scrapy, please refer to the `scrapy-splash library`_.

Support
-------

Open source support is provided here in GitHub. Please `create a question
issue`_.

Commercial support is also available by `Scrapinghub`_.

.. _create a question issue: https://github.com/scrapinghub/splash/issues/new?labels=question
.. _Scrapinghub: https://scrapinghub.com
.. _scrapy-splash library: https://github.com/scrapy-plugins/scrapy-splash

Building qtwebkit from sources
------------------------------

There is a container to build custom binaries from qtwebkit sources. The recipe
is :::

    docker build --target qtwebkitbuilder-base . -t qtwebkit-builder
    git clone git@github.com:qtwebkit/qtwebkit.git ../qtwebkit
    docker run --rm -it -v `pwd`/../qtwebkit:/qtwebkit qtwebkit-builder
     # inside container
     > cd /qtwebkit
     > mkdir build
     > cd build
     > cmake -G Ninja -DPORT=Qt -DCMAKE_BUILD_TYPE=Release ..
     > ninja -j 8
     > ninja install
     > /tmp/create-package.sh install_manifest.txt '' 7z
     > 7z l -ba build.7z  | head -n  10
     2020-05-29 13:57:20 D....            0            0  include
     2020-05-29 13:57:20 D....            0            0  include/QtWebKit
     2020-05-29 13:57:20 D....            0            0  include/QtWebKit/5.212.0
     2020-05-29 13:57:20 D....            0            0  include/QtWebKit/5.212.0/QtWebKit
     2020-05-29 13:57:20 D....            0            0  include/QtWebKit/5.212.0/QtWebKit/private
     2020-05-29 13:57:20 D....            0            0  include/QtWebKitWidgets
     2020-05-29 13:57:20 D....            0            0  include/QtWebKitWidgets/5.212.0
     2020-05-29 13:57:20 D....            0            0  include/QtWebKitWidgets/5.212.0/QtWebKitWidgets
     2020-05-29 13:57:20 D....            0            0  include/QtWebKitWidgets/5.212.0/QtWebKitWidgets/private
     2020-05-29 13:57:20 D....            0            0  lib

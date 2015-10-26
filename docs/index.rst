=======================================
Splash - A javascript rendering service
=======================================

Splash is a javascript rendering service. It's a lightweight web browser
with an HTTP API, implemented in Python using Twisted and QT. The (twisted)
QT reactor is used to make the sever fully asynchronous allowing
to take advantage of webkit concurrency via QT main loop. Some of Splash
features:

* process multiple webpages in parallel;
* get HTML results and/or take screenshots;
* turn OFF images or use Adblock Plus rules to make rendering faster;
* execute custom JavaScript in page context;
* write Lua browsing :ref:`scripts <scripting-tutorial>`;
* develop Splash Lua scripts in :ref:`Splash-Jupyter <splash-jupyter>`
  Notebooks.
* get detailed rendering info in HAR format.


Documentation
=============

.. toctree::
   :maxdepth: 2

   install
   api
   scripting-tutorial
   scripting-ref
   scripting-response-object
   scripting-request-object
   scripting-binary-data
   scripting-libs
   kernel
   faq
   development
   changes


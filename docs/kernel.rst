.. _splash-jupyter:

Splash and Jupyter
==================

Splash provides a custom Jupyter_ (previously known as IPython_) kernel for Lua.
Together with Jupyter notebook_ frontend it forms an interactive
web-based development environment for Splash Scripts with syntax highlighting,
smart code completion, context-aware help, inline images support and a real
live WebKit browser window with Web Inspector enabled, controllable from
a notebook.

Installation
------------

To install Splash-Jupyter using Docker, run::

    $ docker pull scrapinghub/splash-jupyter

Then start the container::

    $ docker run -p 8888:8888 -it scrapinghub/splash-jupyter

.. note::

    Without ``-it`` flags you won't be able to stop the container using Ctrl-C.

This command should print something like this::

    Copy/paste this URL into your browser when you connect for the first time,
    to login with a token:
        http://localhost:8888/?token=e2435ae336d22b23d5e868d03ce728bc33e73b6159e391ba

To view Jupyter, open the suggested location in a browser.
It should display an usual Jupyter Notebook overview page.

.. note::

    In older Docker setups (e.g. with boot2docker_ on OS X) you may have
    to replace 'localhost' with the IP address Docker is available on,
    e.g. a result of ``boot2docker ip`` in case of boot2docker or
    ``docker-machine ip <your machine>`` in case of docker-machine_.

Click "New" button and choose "Splash" in the drop-down list - Splash Notebook
should open.

Splash Notebook looks like an IPython notebook or other Jupyter-based
notebooks; it allows to run and develop Splash Lua scripts interactively.
For example, try entering ``splash:go("you-favorite-website")`` in a cell,
execute it, then enter ``splash:png()`` in the next cell and run it
as well - you should get a screenshot of the website displayed inline.

Persistence
-----------

By default, notebooks are stored in a Docker container; they are destroyed
when you restart an image. To persist notebooks you can mount a local folder
to ``/notebooks``. For example, let's use current folder to store the
notebooks::

    $ docker run -v `/bin/pwd`/notebooks:/notebooks -p 8888:8888 -it splash-jupyter


Live Webkit window
------------------

To view Live Webkit window with web inspector when Splash-Jupyter is executed
from Docker, you will need to pass additional docker parameters to share the
host system's X server with the docker container, and use the ``--disable-xvfb``
command line flag::

    $ docker run -e DISPLAY=unix$DISPLAY \
                 -v /tmp/.X11-unix:/tmp/.X11-unix \
                 -v $XAUTHORITY:$XAUTHORITY \
                 -e XAUTHORITY=$XAUTHORITY \
                 -p 8888:8888 \
                 -it scrapinghub/splash-jupyter --disable-xvfb

.. note::

    The command above is tested on Linux.

From Notebook to HTTP API
-------------------------

After you finished developing the script using Splash Notebook,
you may want to convert it to a form suitable for submitting
to Splash HTTP API (see :ref:`execute` and :ref:`run`).

To do that, copy-paste (or download using "File -> Download as -> .lua")
all relevant code. For :ref:`run` endpoint add ``return`` statement to
return the final result:

.. code-block:: lua

    -- Script code goes here,
    -- including all helper functions.
    return {...}  -- return the result

For :ref:`execute` add ``return`` statement and put the code
inside ``function main(splash)``:

.. code-block:: lua

    function main(splash)
        -- Script code goes here,
        -- including all helper functions.
        return {...}  -- return the result
    end

To make the script more generic you can use :ref:`splash-args` instead of
hardcoded constants (e.g. for page urls). Also, consider submitting several
requests with different arguments instead of running a loop in a script
if you need to visit and process several pages - it is an easy way
to parallelize the work.

There are some gotchas:

1. When you run a notebook cell and then run another notebook cell there
   is a delay between runs; the effect is similar to inserting
   :ref:`splash-wait` calls at the beginning of each cell.
2. Regardless of :ref:`sandbox <lua-sandbox>` settings, scripts in Jupyter
   notebook are **not** sandboxed. Usually it is not a problem,
   but some functions may be unavailable in HTTP API if sandbox is enabled.

.. _IPython: http://ipython.org/
.. _Jupyter: http://jupyter.org/
.. _notebook: http://ipython.org/notebook.html
.. _Docker: http://docker.io
.. _Boot2Docker: http://boot2docker.io/
.. _docker-machine: https://docs.docker.com/machine/

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

If you're on Linux, Jupyter server with Splash kernel enabled
will be available at http://0.0.0.0:8888.

If you use boot2docker_, run ``$ boot2docker ip`` to get the ip address,
the visit http://<ip-returned-by-boot2docker>:8888. If you use
docker-machine_, run ``$ docker-machine ip <your machine>`` to get the ip.

By default, notebooks are stored in a Docker container; they are destroyed
when you restart an image. To persist notebooks you can mount a local folder
to ``/notebooks``. For example, let's use current folder to store the
notebooks::

    $ docker run -v `/bin/pwd`/notebooks:/notebooks -p 8888:8888 -it splash-jupyter

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

Alternatively, to enable live Webkit window you can install Splash
in a "manual way" - see :ref:`manual-install-ubuntu`.

1. Install IPython/Jupyter with notebook feature. Splash kernel requires
   IPython 4.x::

       $ pip3 install 'ipython[notebook] >= 4.1.2, < 5.0'

2. Make sure Splash is installed: run ``pip3 install -U splash``. If you use
   Splash master branch run ``pip3 install -U .`` from source checkout
   instead.

3. Let IPython know about Splash kernel by running the following command::

       $ python3 -m splash.kernel install

To run IPython with Splash notebook, first start IPython notebook and then
create a new Splash notebook using "New" button.

From Notebook to HTTP API
-------------------------

After you finished developing the script using a Jupyter Notebook,
you may want to convert it to a form suitable for submitting
to Splash HTTP API (see :ref:`execute`).

To do that, copy-paste (or download using "File -> Download as -> .lua")
all relevant code, then put it inside ``function main(splash)``:

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

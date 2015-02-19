# -*- coding: utf-8 -*-
"""
To install the kernel type

    $ python -m splash.kernel install

To start the kernel, use IPython web interface or run

    $ python -m splash.kernel

"""
from __future__ import absolute_import
import sys
from .kernel import start, install

if len(sys.argv) > 1 and sys.argv[1] == 'install':
    install()
else:
    start()

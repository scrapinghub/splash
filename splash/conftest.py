# -*- coding: utf-8 -*-
from __future__ import absolute_import
from splash import lua
import glob

collect_ignore = []

if not lua.is_supported():
    collect_ignore = [
        'lua.py',
        'lua_runner.py',
        'lua_runtime.py',
        'qtrender_lua.py',
        'kernel/completer.py',
        'kernel/kernel.py',
        'kernel/__main__.py',
        'kernel/__init__.py',
    ]

collect_ignore.extend([
    'benchmark/download_sites.py',
    'benchmark/file_server.py',
    'benchmark/benchmark.py'])

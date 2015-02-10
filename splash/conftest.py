# -*- coding: utf-8 -*-
from __future__ import absolute_import
from splash import lua

collect_ignore = []

if not lua.is_supported():
    collect_ignore = ['lua.py', 'qtrender_lua.py']

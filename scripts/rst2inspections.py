#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This script extracts inspections info for IPython kernel from
Splash reference documentation.
"""
from __future__ import absolute_import
import os
import re
import json
import collections


def _parse_doc(doc):
    res = collections.OrderedDict()

    m = re.search("^splash:(\w+)\s+[-]+\s*$", doc, re.MULTILINE)
    res['name'] = m.group(1) if m else None

    header, content = re.split("[-][-]+", doc, maxsplit=1)
    res['header'] = header.strip()
    res['content'] = content.strip()

    m = re.search(r"((.|[\n\r])+?)\*\*Signature", content, re.MULTILINE)
    res['short'] = m.group(1).strip() if m else None

    m = re.search(r"Signature:.*``(.+)``", content)
    res['signature'] = m.group(1) if m else None

    m = re.search(r"Returns:\*\*((.|[\n\r])+?)\n\n", content, re.MULTILINE)
    res['returns'] = m.group(1).strip() if m else None

    m = re.search(r"Async:\*\*((.|[\n\r])+?)\n\n", content, re.MULTILINE)
    res['async'] = m.group(1).strip() if m else None

    m = re.search(r"(?:.|[\n\r])*:\*\*(?:.|[\n\r])+?\n\n?((?:.|[\n\r])+)", content, re.MULTILINE)
    res['details'] = m.group(1).strip() if m else None

    m = re.search(r"Parameters:\*\*((.|[\n\r])+?)\*\*Returns:", content, re.MULTILINE)
    res['params'] = m.group(1).strip() if m else None

    return res


def parse_rst(rst_source):
    """
    Parse Sphinx Lua splash methods reference docs and
    extract information useful for inspections.
    """
    parsed = re.split("\.\. _splash-(.+):", rst_source)[1:]
    # ids = parsed[::2]
    docs = parsed[1::2]
    info = [_parse_doc(d) for d in docs]
    return collections.OrderedDict(
        (d["header"], d)
        for d in info
    )


def resolve_literalinclude(rst_source, base_dir):
    pattern = r"\.\. literalinclude::\s*(.+)\n\s*:language:.+\n"
    def repl(m):
        path = m.group(1)
        with open(os.path.join(base_dir, path), 'rb') as f:
            return f.read().decode('utf8')

    return re.sub(pattern, repl, rst_source)


def rst2inspections(rst_filename, out_filename):
    with open(rst_filename, "rb") as f:
        doc = f.read().decode('utf8')
        doc = resolve_literalinclude(doc, os.path.dirname(rst_filename))
        info = parse_rst(doc)

    with open(out_filename, "w") as f:
        json.dump(info, f, indent=2)


if __name__ == '__main__':
    root = os.path.join(os.path.dirname(__file__), "..")
    rst_filename = os.path.join(root, "docs", "scripting-ref.rst")
    out_filename = os.path.join(root, "splash", "kernel", "inspections", "splash-auto.json")
    rst2inspections(rst_filename, out_filename)


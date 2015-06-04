# -*- coding: utf-8 -*-
"""
Autocompleter for Lua code.
"""
from __future__ import absolute_import
import string

from splash.utils import dedupe
from splash.kernel.lua_parser import (
    LuaParser,
    Standalone,
    ObjectAttribute,
    ObjectAttributeIndexed,
    ObjectIndexedComplete,
    ObjectMethod,
    SplashAttribute,
    SplashMethod,
    ConstantMethod,
)


LUA_KEYWORDS = {
    'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for',
    'function', 'if', 'in', 'local', 'nil', 'not', 'or', 'repeat',
    'return', 'then', 'true', 'until', 'while'
}

DONT_SUGGEST_METHODS = {'_create'}


class Completer(object):
    def __init__(self, lua):
        self.lua = lua
        self.completer = self.lua.eval("require('completer')")
        self.parser = LuaParser(lua)

    def parse(self, code, cursor_pos):
        return self.parser.parse(code, cursor_pos)

    def complete(self, code, cursor_pos):
        NO_SUGGESTIONS = {
            'matches': [],
            'cursor_end': cursor_pos,
            'cursor_start': cursor_pos,
            'metadata': {},
            'status': 'ok',
        }
        prev_char = code[cursor_pos-1:cursor_pos]

        if prev_char in string.whitespace:
            return NO_SUGGESTIONS

        m = self.parse(code, cursor_pos)
        if m is None:
            return NO_SUGGESTIONS

        matches = []

        if isinstance(m, Standalone):
            matches += self.complete_keyword(m.value)
            matches += self.complete_local_identifier(code, m.value)
            matches += self.complete_global_variable(m.value)

        elif isinstance(m, ConstantMethod):
            matches += self.complete_obj_method(m.const, m.prefix)

        elif isinstance(m, ObjectIndexedComplete):
            return NO_SUGGESTIONS

        elif hasattr(m, 'names_chain'):
            names_chain = self.lua.table_from(m.names_chain)

            if isinstance(m, ObjectAttribute):
                matches += self.complete_any_attribute(names_chain, m.prefix)

            if isinstance(m, ObjectAttributeIndexed):
                matches += [
                    "%s%s]" % (el, m.quote)
                    for el in self.complete_any_attribute(names_chain, m.prefix)
                ]

            elif isinstance(m, ObjectMethod):
                matches += self.complete_method(names_chain, m.prefix)

            elif isinstance(m, SplashMethod):
                matches += [
                    el for el in self.complete_method(names_chain, m.prefix)
                    if el not in DONT_SUGGEST_METHODS
                ]

            elif isinstance(m, SplashAttribute):
                matches += [
                    el for el in self.complete_non_method(names_chain, m.prefix)
                    if not el.startswith("_")
                ]

        return {
            'matches': list(dedupe(matches)),
            'cursor_end': cursor_pos,
            'cursor_start': cursor_pos - len(getattr(m, "prefix", "")),
            'metadata': {},
            'status': 'ok',
        }

    def complete_any_attribute(self, names_chain, prefix=""):
        attrs = self.completer.attrs(names_chain, False, False)
        return sorted_with_prefix(prefix, attrs.values())

    def complete_non_method(self, names_chain, prefix=""):
        attrs = self.completer.attrs(names_chain, True, False)
        return sorted_with_prefix(prefix, attrs.values())

    def complete_method(self, names_chain, prefix=""):
        methods = self.completer.attrs(names_chain, False, True)
        return sorted_with_prefix(prefix, methods.values())

    def complete_obj_method(self, value, prefix=""):
        methods = self.completer.obj_attrs(value, False, True)
        return sorted_with_prefix(prefix, methods.values())

    def complete_keyword(self, prefix):
        return sorted_with_prefix(prefix, LUA_KEYWORDS)

    def complete_global_variable(self, prefix):
        g = self.lua.globals()
        return sorted_with_prefix(prefix, g.keys())

    def complete_local_identifier(self, code, prefix):
        return sorted_with_prefix(prefix, self._local_identifiers(code))

    def _local_identifiers(self, code):
        """ yield all Lua identifiers """
        tokens = self.parser.lexer.tokenize(code, pad=1)
        for idx, tok in enumerate(tokens[1:], start=1):
            prev = tokens[idx-1]
            if tok.type == 'iden' and prev.type not in '.:':
                yield tok.value


def sorted_with_prefix(prefix, it, drop_exact=True, drop_special=True):
    """
    >>> sorted_with_prefix("foo", ["fooZ", "fooAA", "fox"])
    ['fooAA', 'fooZ']
    >>> sorted_with_prefix("", ["fooZ", "fooAA", "_f", "__f", "fox"])
    ['fooAA', 'fooZ', 'fox', '_f']
    >>> sorted_with_prefix("", ["fooZ", "fooAA", "_f", "__f", "fox"], drop_special=False)
    ['fooAA', 'fooZ', 'fox', '_f', '__f']
    """
    key = lambda name: (name.startswith("__"), name.startswith("_"), name)
    return sorted([
        el for el in it
        if el.startswith(prefix) and (not drop_exact or el != prefix)
           and (not drop_special or not el.startswith("__"))
    ], key=key)


# XXX: how to print debug messages in IPython kernels???
def _pp(*args):
    txt = "\n" + "\n".join(map(repr, args)) + "\n"
    raise Exception(txt)




# -*- coding: utf-8 -*-
from __future__ import absolute_import
from collections import namedtuple
import sys
from splash.utils import dedupe

Tok = namedtuple("Tok", "type value")
SplashTok = Tok("iden", "splash")


LUA_KEYWORDS = {
    'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for',
    'function', 'if', 'in', 'local', 'nil', 'not', 'or', 'repeat',
    'return', 'then', 'true', 'until', 'while'
}


class Completer(object):
    def __init__(self, lua):
        self.lua = lua
        self._completer = self.lua.eval("require('completer')")

    def tokenize(self, lua_source, pad=0):
        res = self._completer.tokenize(lua_source)
        tokens = [Tok(t["tp"], t["value"]) for t in res.values()]
        return [Tok("NA", "")] * pad + tokens

    def _context(self, code, cursor_pos):
        """ Return text on the same line, left to the cursor """
        return code[:cursor_pos].split("\n")[-1]

    def complete(self, code, cursor_pos):
        matches = []
        prefix = ""

        text = self._context(code, cursor_pos)
        tokens = self.tokenize(text, pad=3)
        types = [t.type for t in tokens]
        prev2, prev, cur = tokens[-3:]

        if types[-2:] == ['iden', '.']:
            if prev == SplashTok:
                matches += self.complete_non_method(prev.value)
            else:
                matches += self.complete_any_attribute(prev.value)

        elif types[-3:] == ['iden', '.', 'iden']:
            prefix = cur.value
            if prev == SplashTok:
                matches += self.complete_non_method(prev.value, prefix)
            else:
                matches += self.complete_any_attribute(prev2.value, prefix)

        elif types[-2:] == ['iden', ':']:
            matches += self.complete_method(prev.value)

        elif types[-3:] == ['iden', ':', 'iden']:
            prefix = cur.value
            matches += self.complete_method(prev2.value, prefix)

        if (prev.type not in '.:') and cur.type == 'iden':
            prefix = cur.value
            matches += self.complete_keyword(prefix)
            matches += self.complete_local_identifier(code, prefix)
            matches += self.complete_global_variable(prefix)

        # _pp(tokens[3:], types[-3:], prev, cur, matches)
        return {
            'matches': dedupe(matches),
            'cursor_end': cursor_pos,
            'cursor_start': cursor_pos - len(prefix),
            'metadata': {},
            'status': 'ok',
        }

    def complete_any_attribute(self, obj_name, prefix=""):
        attrs = self._completer.attrs(obj_name, False, False)
        return sorted_with_prefix(prefix, attrs.values())

    def complete_non_method(self, obj_name, prefix=""):
        attrs = self._completer.attrs(obj_name, True, False)
        return sorted_with_prefix(prefix, attrs.values())

    def complete_method(self, obj_name, prefix=""):
        methods = self._completer.attrs(obj_name, False, True)
        return sorted_with_prefix(prefix, methods.values())

    def complete_keyword(self, prefix):
        return sorted_with_prefix(prefix, LUA_KEYWORDS)

    def complete_global_variable(self, prefix):
        return sorted_with_prefix(prefix, self.lua.globals())

    def complete_local_identifier(self, code, prefix):
        return sorted_with_prefix(prefix, [
            t for t in self._local_identifiers(code) if t != prefix
        ])

    def _local_identifiers(self, code):
        """ yield all Lua identifiers """
        tokens = self.tokenize(code, pad=1)
        for idx, tok in enumerate(tokens[1:], start=1):
            prev = tokens[idx-1]
            if tok.type == 'iden' and prev.type not in '.:':
                yield tok.value


def sorted_with_prefix(prefix, it):
    """
    >>> sorted_with_prefix("foo", ["fooZ", "fooAA", "fox"])
    ['fooAA', 'fooZ']
    """
    return sorted([el for el in it if el.startswith(prefix)])


# XXX: how to print debug messages in IPython kernels???
def _pp(*args):
    txt ="\n" + "\n".join(map(repr,args)) + "\n"
    raise Exception(txt)




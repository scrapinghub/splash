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

        attr_chain = self._attr_chain(tokens)

        # 'splash' object is special-cased: we know that its methods
        # should be called only using splash:foo() syntax, so methods
        # are not suggested for splash.foo().
        # This may be changed if error handling changes - pcall could
        # require writing "splash.foo".
        if len(attr_chain) == 2 and types[-2:] == ['iden', '.'] and prev == SplashTok:
            names_chain = self.lua.table_from([prev.value])
            matches += self.complete_non_method(names_chain)

        elif len(attr_chain) == 3 and types[-3:] == ['iden', '.', 'iden'] and prev2 == SplashTok:
            prefix = cur.value
            names_chain = self.lua.table_from([prev2.value])
            matches += self.complete_non_method(names_chain, prefix)

        elif attr_chain:
            prefix = ""
            lookup_type = "."

            if len(attr_chain) != 1:
                if attr_chain[-1].type == 'iden':
                    prefix = attr_chain[-1].value
                    attr_chain.pop()  # pop the prefix

                lookup_type = attr_chain.pop().type
                assert lookup_type in ".:"

            names = [t.value for t in attr_chain if t.type == 'iden']
            attr_chain = self.lua.table_from(names)

            if lookup_type == ".":
                matches += self.complete_any_attribute(attr_chain, prefix)
            elif lookup_type == ":":
                matches += self.complete_method(attr_chain, prefix)
            else:
                raise ValueError("invalid lookup_type")

        if (prev.type not in '.:') and cur.type == 'iden':
            # standalone identifier
            prefix = cur.value
            matches += self.complete_keyword(prefix)
            matches += self.complete_local_identifier(code, prefix)
            matches += self.complete_global_variable(prefix)

        return {
            'matches': list(dedupe(matches)),
            'cursor_end': cursor_pos,
            'cursor_start': cursor_pos - len(prefix),
            'metadata': {},
            'status': 'ok',
        }

    def _attr_chain(self, tokens):
        chain = []
        state = "start"
        for tok in reversed(tokens):
            if tok.type in ".:":
                if state == "dot":
                    return []  # invalid chain: two consequent separators
                state = "dot"
                chain.append(tok)
            elif tok.type == "iden":
                if state == "iden":
                    return []  # invalid chain: two consequent identifiers
                state = "iden"
                chain.append(tok)
            else:
                break

        chain.reverse()

        # no identifiers found => nothing to complete
        if sum(1 for t in chain if t.type == 'iden') == 0:
            return []

        # only a single : is allowed, near the end of the chain
        if any(t.type == ":" for t in chain[:-2]):
            return []

        # leading "." means we're not completing an object attribute
        if chain[0].type != "iden":
            return []

        return chain

    def complete_any_attribute(self, names_chain, prefix=""):
        attrs = self._completer.attrs(names_chain, False, False)
        return sorted_with_prefix(prefix, attrs.values())

    def complete_non_method(self, names_chain, prefix=""):
        attrs = self._completer.attrs(names_chain, True, False)
        return sorted_with_prefix(prefix, attrs.values())

    def complete_method(self, names_chain, prefix=""):
        methods = self._completer.attrs(names_chain, False, True)
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




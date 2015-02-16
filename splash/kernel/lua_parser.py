# -*- coding: utf-8 -*-
"""
Parser for a subset of Lua, useful for autocompletion.
It takes ``Tok(name, value)`` namedtuples as an input.
"""
from __future__ import absolute_import
import string
from operator import attrgetter
from collections import namedtuple

from funcparserlib import parser as p


Token = namedtuple("Token", "type value")


class _Match(object):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.value)


class _AttrLookupMatch(_Match):
    @property
    def prefix(self):
        return self.value[0]

    @property
    def names_chain(self):
        return self.value[1:][::-1]

    def __repr__(self):
        return "%s(prefix=%r names_chain=%r)" % (
            self.__class__.__name__, self.prefix, self.names_chain
        )


class Standalone(_Match):
    pass

class SplashAttribute(_AttrLookupMatch):
    pass

class SplashMethod(_AttrLookupMatch):
    pass

class ObjectAttribute(_AttrLookupMatch):
    pass

class ObjectAttributeIndexed(object):
    def __init__(self, value):
        self.quote = value[1]
        self.prefix = value[0]
        self.names_chain = value[2:][::-1]

    def __repr__(self):
        return "%s(prefix=%r names_chain=%r, quote=%r)" % (
            self.__class__.__name__, self.prefix, self.names_chain, self.quote
        )

class ObjectMethod(_AttrLookupMatch):
    pass


# ======================== processing functions =============================

token_value = attrgetter("value")
token_type = attrgetter("type")

def token(tp, check=lambda t: True):
    return p.some(lambda t: t.type == tp and check(t)) >> token_value

def flat(seq):
    res = []
    for el in seq:
        if isinstance(el, (list, tuple)):
            res.extend([sub_el for sub_el in flat(el)])
        else:
            res.append(el)
    return res

def match(cls):
    return lambda res: cls(res)

# =============================== parser ====================================

# A partial parser for Lua.
#
# It works on a *reversed* sequence of tokens
# (right to left), starting from a token at cursor.

tok_number = token("number")
tok_string = token("string")
dot = token(".")
colon = token(":")
single_quote = token('"')
double_quote = token("'")
quote = (single_quote | double_quote)
open_sq_brace = token("[")
close_sq_brace = token("]")

iden_start = p.skip(p.some(lambda t: t.type not in ".:"))

tok_splash = (p.a(Token("iden", "splash")) + iden_start) >> token_value
iden_nosplash = token("iden", lambda t: t.value != 'splash')
iden = token("iden")

# standalone names are parsed separately - we need e.g. to suggest them
# as keywords
first_iden = iden + iden_start
single_obj = first_iden >> match(Standalone)

_index = p.skip(close_sq_brace) + (tok_string | tok_number) + p.skip(open_sq_brace)
dot_iden_or_index = _index | (iden + p.skip(dot))   # either .name or ["name"]

# foo[0]["bar"].baz
_attr_chain = p.oneplus(dot_iden_or_index) + first_iden
_obj = _attr_chain | first_iden
_attr_chain_noprefix = p.pure("") + p.skip(dot) + _obj
obj_attr_chain = (_attr_chain | _attr_chain_noprefix) >> flat >> match(ObjectAttribute)

# foo["bar
_indexed = quote + p.skip(open_sq_brace) + _obj
_obj_attr_indexed_noprefix = p.pure("") + _indexed
_obj_attr_indexed = iden + _indexed  # FIXME: spaces in keys
obj_attr_indexed = (_obj_attr_indexed | _obj_attr_indexed_noprefix) >> flat >> match(ObjectAttributeIndexed)

# foo.bar:baz
_obj_method = iden + p.skip(colon) + _obj
_obj_method_noprefix = p.pure("") + p.skip(colon) + _obj
obj_method = (_obj_method | _obj_method_noprefix) >> flat >> match(ObjectMethod)

# splash:meth
_splash_method = iden_nosplash + p.skip(colon) + tok_splash
_splash_method_noprefix = p.pure("") + p.skip(colon) + tok_splash
splash_method = (_splash_method | _splash_method_noprefix) >> match(SplashMethod)

# splash.attr
_splash_attr = iden_nosplash + p.skip(dot) + tok_splash
_splash_attr_noprefix = p.pure("") + p.skip(dot) + tok_splash
splash_attr = (_splash_attr | _splash_attr_noprefix) >> match(SplashAttribute)

splash_parser = splash_method | splash_attr
lua_parser = (splash_parser | obj_method | obj_attr_indexed | obj_attr_chain | single_obj)

# ========================= wrapper objects =================================

class LuaLexer(object):
    def __init__(self, lua):
        self._completer = lua.eval("require('completer')")

    def tokenize(self, lua_source, pad=1):
        # Our lexer doesn't support unicode. To avoid exceptions,
        # replace all non-ascii characters before the tokenization.
        # This is not optimal, but Lua doesn't allow unicode identifiers,
        # so non-ascii text usually is not interesting for the completion
        # engine.
        lua_source = lua_source.encode('ascii', 'replace')
        res = self._completer.tokenize(lua_source)
        return [Token("NA", "")]*pad + [Token(t["tp"], t["value"]) for t in res.values()]


class LuaParser(object):
    out_chars = string.whitespace + ".,:;\"')([]/*+^-=&%{}<>~"

    def __init__(self, lua):
        self.lexer = LuaLexer(lua)

    def parse(self, code, cursor_pos=None):
        if cursor_pos is None:
            cursor_pos = len(code)

        if self._token_split(code, cursor_pos):
            return

        context = code[:cursor_pos]
        tokens = self.lexer.tokenize(context, pad=1)
        try:
            return lua_parser.parse(tokens[::-1])
        except p.NoParseError as e:
            return

    def _token_split(self, code, cursor_pos):
        """ Return True if a token is split into two parts by cursor_pos """
        next_char = code[cursor_pos:cursor_pos+1]
        return next_char and next_char not in self.out_chars

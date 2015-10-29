# -*- coding: utf-8 -*-
"""
Parser for a subset of Lua, useful for autocompletion.
"""
from __future__ import absolute_import
import string
from operator import attrgetter
from collections import namedtuple

from funcparserlib import parser as p

# ===================== Helper data structures ==============================
from splash.utils import to_bytes

Token = namedtuple("Token", "type value")


class _Match(object):
    def __init__(self, value):
        self.value = value

    @classmethod
    def match(cls, p):
        return p >> flat >> match(cls)

    def __eq__(self, other):
        if other is None:
            return False
        if not isinstance(other, _Match):
            raise TypeError("can't compare objects")
        return self.value == other.value and self.__class__ == other.__class__

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.value)


class _AttrLookupMatch(_Match):
    prefix_index = 0

    @property
    def prefix(self):
        return self.value[self.prefix_index]

    @property
    def names_chain(self):
        start = self.prefix_index + 1
        return self.value[start:][::-1]

    def __repr__(self):
        return "%s(prefix=%r names_chain=%r)" % (
            self.__class__.__name__, self.prefix, self.names_chain
        )


class Standalone(_Match):
    @property
    def prefix(self):
        return self.value

class SplashAttribute(_AttrLookupMatch):
    pass

class SplashMethod(_AttrLookupMatch):
    pass

class SplashMethodOpenBrace(_AttrLookupMatch):
    pass

class ObjectAttribute(_AttrLookupMatch):
    pass

class ObjectAttributeIndexed(_Match):
    def __init__(self, value):
        super(ObjectAttributeIndexed, self).__init__(value)
        self.quote = value[1]
        self.prefix = value[0]
        self.names_chain = value[2:][::-1]

    def __repr__(self):
        return "%s(prefix=%r names_chain=%r, quote=%r)" % (
            self.__class__.__name__, self.prefix, self.names_chain, self.quote
        )

class ObjectIndexedComplete(_Match):
    pass

class ObjectMethod(_AttrLookupMatch):
    pass

class ConstantMethod(_Match):
    def __init__(self, value):
        super(ConstantMethod, self).__init__(value)
        self.prefix, self.const = value

    def __repr__(self):
        return "%s(prefix=%r const=%r)" % (
            self.__class__.__name__, self.prefix, self.const)


# ======================== Processing functions =============================

token_value = attrgetter("value")
token_type = attrgetter("type")

def token(tp):
    return p.some(lambda t: t.type == tp) >> token_value

def flat(seq):
    res = []
    if not isinstance(seq, (list, tuple)):
        return seq
    for el in seq:
        if isinstance(el, (list, tuple)):
            res.extend([sub_el for sub_el in flat(el)])
        else:
            res.append(el)
    return res

def match(cls):
    return lambda res: cls(res)


# =============================== Grammar ====================================

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
open_rnd_brace = token("(")
close_rnd_brace = token(")")

tok_constant = p.some(lambda t: t.value in {'nil', 'true', 'false'})
iden_start = p.skip(p.some(lambda t: t.type not in ".:"))
tok_splash = (p.a(Token("iden", "splash")) + iden_start) >> token_value
iden = token("iden")
opt_iden = iden | p.pure("")

# =========== Expressions parser
# FIXME: it should be rewritten using full Lua 5.2 grammar.

BINARY_OPS = set("+-*/^%><") | {"..", "==", "~=", ">=", "<=", "and", "or"}
UNARY_OPS = {"not", "-", "#"}

binary_op = p.some(lambda t: t.value in BINARY_OPS) >> token_value
unary_op = p.some(lambda t: t.value in UNARY_OPS) >> token_value

# expressions with binary and unary ops + parenthesis
@p.with_forward_decls
def value():
    single_value = table | tok_number | tok_string | tok_constant | iden
    return single_value | (close_rnd_brace + expr + open_rnd_brace)
_term = value + p.skip(p.maybe(unary_op))
expr = _term + p.many(binary_op + _term) >> flat

# [expression]
_index_lookup = p.skip(close_sq_brace) + expr + p.skip(open_sq_brace)

# foo=expr
# [foo]=expr
_key = iden | _index_lookup
_keyvalue = expr + token("=") + _key

# foo=expr, ["bar"]=42,
_table_sep = token(",") | token(";")
table_parameters = (
    p.maybe(_table_sep) +   # allow trailing comma/semicolon
    (_keyvalue | expr) +
    p.many(_table_sep + (_keyvalue | expr))
)

# table constructor, with and without closing }
table_incomplete = (p.maybe(table_parameters) + token("{")) >> flat
table = (token("}") + table_incomplete) >> flat

# ======== end expression parser

# standalone names are parsed separately - we need e.g. to suggest them
# as keywords
first_iden = iden + iden_start
single_obj = Standalone.match(first_iden)

# ("hello"):len
constant_method = ConstantMethod.match(
    opt_iden +
    p.skip(colon) +
    p.skip(close_rnd_brace) +
    (tok_string | tok_number) +
    p.skip(open_rnd_brace)
)

# ["foo"] or [42]
constant_index_lookup = (
    p.skip(close_sq_brace) +
    (tok_string | tok_number) +
    p.skip(open_sq_brace)
)

# either .name or ["name"]
dot_or_index_lookup = constant_index_lookup | (iden + p.skip(dot))

# foo[0]["bar"].baz
# TODO: cleanup this rule
_attr_chain = p.oneplus(dot_or_index_lookup) + first_iden
_obj = _attr_chain | first_iden
_attr_chain_noprefix = p.pure("") + p.skip(dot) + _obj
obj_attr_chain = ObjectAttribute.match(_attr_chain | _attr_chain_noprefix)

# foo["bar"]
obj_indexed_complete = ObjectIndexedComplete.match(
    p.skip(close_sq_brace) +
    (tok_string | tok_number) +
    p.skip(open_sq_brace) +
    _obj
)

# foo["bar
obj_attr_indexed = ObjectAttributeIndexed.match(
    opt_iden +      # FIXME: spaces in keys
    quote +
    p.skip(open_sq_brace) +
    _obj
)

# foo.bar:baz
obj_method = ObjectMethod.match(
    opt_iden +
    p.skip(colon) +
    _obj
)

# splash:meth
splash_method = SplashMethod.match(
    opt_iden +
    p.skip(colon) +
    tok_splash
)

# splash:meth(
# splash:meth{
# splash:meth{foo=bar,
_splash_method_open_posargs = (
    p.skip(token("(")) +
    iden +
    p.skip(colon) +
    tok_splash
)
_splash_method_open_named_args = (
    p.skip(table_incomplete) +
    iden +
    p.skip(colon) +
    tok_splash
)
splash_method_open_brace = SplashMethodOpenBrace.match(
    _splash_method_open_posargs |
    _splash_method_open_named_args
)


# splash.attr
splash_attr = SplashAttribute.match(
    opt_iden +
    p.skip(dot) +
    tok_splash
)

lua_parser = (
      splash_method
    | splash_method_open_brace
    | splash_attr
    | obj_method
    | obj_indexed_complete
    | obj_attr_indexed
    | obj_attr_chain
    | constant_method
    | single_obj
)

# ========================= Wrapper objects =================================

class LuaLexer(object):
    def __init__(self, lua):
        self.lua = lua
        self._completer = lua.eval("require('completer')")

    def tokenize(self, lua_source, pad=1):
        # Our lexer doesn't support unicode. To avoid exceptions,
        # replace all non-ascii characters before the tokenization.
        # This is not optimal, but Lua doesn't allow unicode identifiers,
        # so non-ascii text usually is not interesting for the completion
        # engine.
        lua_source = to_bytes(lua_source, 'ascii', 'replace')
        res = self._completer.tokenize(lua_source)
        padding = [Token("NA", "")] * pad
        tokens = [
            Token(
                self.lua.lua2python(t[b"tp"], encoding='utf8'),
                self.lua.lua2python(t[b"value"], encoding='utf8'),
            )
            for t in res.values()
        ]
        return padding + tokens


class LuaParser(object):
    out_chars = string.whitespace + ".,:;\"')([]/*+^-=&%{}<>~"

    def __init__(self, lua):
        self.lexer = LuaLexer(lua)

    def parse(self, code, cursor_pos=None, allow_inside=False):
        if cursor_pos is None:
            cursor_pos = len(code)

        if not allow_inside and self._token_split(code, cursor_pos):
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

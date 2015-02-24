# -*- coding: utf-8 -*-
"""
A complete parser for Lua 5.2 grammar. It is based on grammar as described in
http://www.lua.org/manual/5.2/manual.html#9.

Left recursion is eliminated to make the grammar compatible
with top-down parser which funcparserlib uses.

This grammar works on straight sequence of tokens, so it is not suitable
for autocompletion.

The parser is not concerned with operator precedence.

.. warning:

    This parser is experimental and untested!

"""
from __future__ import absolute_import

from funcparserlib import parser as p

from .common import T, node, Name, String, Number, fieldsep, unop, binop

# ============================ Grammar ====================================

exp = p.forward_decl()
block = p.forward_decl()
explist = p.forward_decl()
var = p.forward_decl()

# field ::= ‘[’ exp ‘]’ ‘=’ exp | Name ‘=’ exp | exp
field = (
    (T('[') + exp + T(']') + T('=') + exp) |
    (Name + T('=') + exp) |
    exp
) >> node('field')


# fieldlist ::= field {fieldsep field} [fieldsep]
fieldlist = field + p.many(fieldsep + field) + p.maybe(fieldsep) >> node("fieldlist")


# tableconstructor ::= ‘{’ [fieldlist] ‘}’
tableconstructor = T('{') + p.maybe(fieldlist) + T('}') >> node('tableconstructor')


# XXX: moved here in order to avoid unnecessary forward declarations
# 	namelist ::= Name {‘,’ Name}
namelist = Name + p.many(T(',') + Name) >> node('namelist')


# parlist ::= namelist [‘,’ ‘...’] | ‘...’
parlist = (
    (namelist + p.maybe(T(',') + T('...'))) |
    T('...')
) >> node('parlist')


# funcbody ::= ‘(’ [parlist] ‘)’ block end
funcbody = T('(') + p.maybe(parlist) + block + T('end') >> node('funcbody')


# functiondef ::= function funcbody
functiondef = T('function') + funcbody >> node('functiondef')


# args ::=  ‘(’ [explist] ‘)’ | tableconstructor | String
args = (
    T('(') + p.maybe(explist) + T(')') |
    tableconstructor |
    String
) >> node('args')


# functioncall ::=  prefixexp args | prefixexp ‘:’ Name args
# prefixexp ::= var | functioncall | ‘(’ exp ‘)’
# var ::=  Name | prefixexp ‘[’ exp ‘]’ | prefixexp ‘.’ Name
#
# left recursion is eliminated like in
# https://github.com/antlr/grammars-v4/blob/master/lua/Lua.g4
#

name_and_args = (
    p.maybe(T(':') + args) + args
) >> node("name_and_args")

var_suffix = (
    p.many(name_and_args) +
    (
        (p.skip(T('[')) + exp + p.skip(T(']')) >> node("index_lookup")) |
        (p.skip(T('.')) + Name) >> node("dot_lookup")
    )
) >> node("var_suffix")

var_or_exp = (var | (T('(') + exp + T(')'))) >> node("var_or_exp")

functioncall = var_or_exp + p.oneplus(name_and_args) >> node('functioncall')

prefixexp = var_or_exp + p.many(name_and_args) >> node('prefixexp')

var.define(
    (Name | (T('(') + exp + T(')') + var_suffix)) + p.many(var_suffix) >> node('var')
)

# exp ::=  nil | false | true | Number | String | ‘...’ | functiondef |
#          prefixexp | tableconstructor | exp binop exp | unop exp
#
# This rule is left-recursive. Left recursion can be eliminated
# using the following method:
#
# (A -> Aa | B)  <=>  (A -> BA');  (A' -> aA' | e)
#
# ============================= Let's do it:
# A := exp
# a := binop + exp
# B := _exp_prefix
_exp_prefix =  (
    (unop + exp) >> node("_exp_unop") |
    tableconstructor |
    prefixexp |
    functiondef |
    T('nil') |
    T('false') |
    T('true') |
    Number |
    String |
    T('...')
) # >> node("_exp_prefix")

_exp_suffix = binop + exp # >> node("_exp_suffix")

exp.define(
    _exp_prefix + p.many(_exp_suffix) >> node('exp')
)
# ============================== done eliminating left recursion.


# explist ::= exp {‘,’ exp}
explist.define(exp + p.many(p.skip(T(',')) + exp) >> node('explist'))


# varlist ::= var {‘,’ var}
varlist = var + p.many(T(',') + var) >> node('varlist')


# 	funcname ::= Name {‘.’ Name} [‘:’ Name]
funcname = Name + p.many(T('.') + Name) + p.maybe(T(':') + Name) >> node('funcname')


# 	label ::= ‘::’ Name ‘::’
label = T('::') + Name + T('::') >> node('label')


# 	retstat ::= return [explist] [‘;’]
retstat = T('return') + p.maybe(explist) + p.maybe(T(';')) >> node('retstat')


# stat ::=  ‘;’ |
#           varlist ‘=’ explist |
#           functioncall |
#           label |
#           break |
#           goto Name |
#           do block end |
#           while exp do block end |
#           repeat block until exp |
#           if exp then block {elseif exp then block} [else block] end |
#           for Name ‘=’ exp ‘,’ exp [‘,’ exp] do block end |
#           for namelist in explist do block end |
#           function funcname funcbody |
#           local function Name funcbody |
#           local namelist [‘=’ explist]
stat = (
    (T('local') + namelist + p.maybe(T('=') + explist)) >> node("local-var") |
    (varlist + T('=') + explist) >> node("assignment") |
    (T('local') + T('function') + Name + funcbody) >> node("local-function") |
    (T('function') + funcname + funcbody) >> node("function") |
    (T('for') + namelist + T('in') + explist + T('do') + block + T('end')) >> node("for-in-loop")|
    (
        T('for') + Name + T('=') + exp + T(',') + exp + p.maybe(T(',') + exp) +
        T('do') + block + T('end')
    ) >> node("for-loop") |
    (
        T('if') + exp + T('then') + block +
        p.many(T('elseif') + exp + T('then') + block) +
        p.maybe(T('else') + block) +
        T('end')
    ) >> node('if-then-else') |
    (T('repeat') + block + T('until') + exp) >> node('repeat-until') |
    (T('while') + exp + T('do') + block + T('end')) >> node('while-loop') |
    (T('do') + block + T('end')) >> node('do-block') |
    (T('goto') + Name) >> node('goto') |
    T('break') |
    label |
    functioncall |
    T(';')
) >> node('stat')


# 	block ::= {stat} [retstat]
block.define((p.many(stat) + p.maybe(retstat)) >> node('block'))


# 	chunk ::= block
chunk = block + p.finished

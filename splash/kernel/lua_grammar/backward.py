# -*- coding: utf-8 -*-
"""
A complete parser for Lua 5.2 grammar. It is based on grammar as described in
http://www.lua.org/manual/5.2/manual.html#9.

Left recursion is eliminated to make the grammar compatible
with top-down parser which funcparserlib uses.

This grammar works on **reversed** sequence of tokens, so it is more suitable
for autocompletion.

The parser is not concerned with operator precedence.

.. warning:

    This parser is experimental and untested!
    Parsing of statements is definitely broken.

"""
from __future__ import absolute_import
from funcparserlib import parser as p

from .common import T, node, Name, String, Number, fieldsep, unop, binop


exp = p.forward_decl()
block = p.forward_decl()
explist = p.forward_decl()
var = p.forward_decl()


# field ::= ‘[’ exp ‘]’ ‘=’ exp | Name ‘=’ exp | exp
field = (
    (exp + T('=') + T(']') + exp + T('[')) |
    (exp + T('=') + Name) |
    exp
) >> node('field')


# fieldlist ::= field {fieldsep field} [fieldsep]
fieldlist = (
    p.maybe(fieldsep) + p.many(field + fieldsep) + field
) >> node("fieldlist")


# tableconstructor ::= ‘{’ [fieldlist] ‘}’
tableconstructor = (
    T('}') + p.maybe(fieldlist) + T('{')
) >> node('tableconstructor')


# XXX: moved here in order to avoid unnecessary forward declarations
# 	namelist ::= Name {‘,’ Name}
namelist = (p.many(Name + T(',')) + Name) >> node('namelist')


# parlist ::= namelist [‘,’ ‘...’] | ‘...’
parlist = (
    (p.maybe(T('...') + T(',')) + namelist) |
    T('...')
) >> node('parlist')


# funcbody ::= ‘(’ [parlist] ‘)’ block end
funcbody = (T('end') + block + T(')') + p.maybe(parlist) + T('(')) >> node('funcbody')


# functiondef ::= function funcbody
functiondef = (funcbody + T('function')) >> node('functiondef')


# args ::=  ‘(’ [explist] ‘)’ | tableconstructor | String
args = (
    (T(')') + p.maybe(explist) + T('(')) |
    tableconstructor |
    String
) >> node('args')


#
# Unlike "forward" grammar, there is no left recursion in
# functioncall/prefixexp/var.
#

# functioncall ::=  prefixexp args | prefixexp ‘:’ Name args
prefixexp = p.forward_decl()
functioncall = (args + Name + T(':') + prefixexp | args + prefixexp) >> node("functioncall")


# prefixexp ::= var | functioncall | ‘(’ exp ‘)’
prefixexp.define((
    functioncall |
    T(')') + exp + T('(') |
    var
) >> node("prefixexp"))


# var ::=  Name | prefixexp ‘[’ exp ‘]’ | prefixexp ‘.’ Name
var.define((
    Name + T('.') + prefixexp |
    T(']') + exp + T('[') + prefixexp |
    Name
) >> node("var"))


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
# a := (binop + exp) | unop
# B := _exp_B

_exp_B =  (
    tableconstructor |
    prefixexp |
    functiondef |
    T('nil') |
    T('false') |
    T('true') |
    Number |
    String |
    T('...')
) # >> node("_exp_B")

# A' -> aA' | e
_exp_A1 = p.maybe(binop + exp | unop) # >> node("_exp_A1")

# A -> BA'
exp.define(_exp_B + _exp_A1 >> node("exp"))

# ============================== done eliminating left recursion.


# explist ::= exp {‘,’ exp}
explist.define(p.many(exp + p.skip(T(','))) + exp >> node('explist'))


# varlist ::= var {‘,’ var}
varlist = p.many(var + T(',')) + var >> node('varlist')


# funcname ::= Name {‘.’ Name} [‘:’ Name]
funcname = p.maybe(Name + T(':')) + p.many(Name + T('.')) + Name >> node('funcname')


# label ::= ‘::’ Name ‘::’
label = T('::') + Name + T('::') >> node('label')


# retstat ::= return [explist] [‘;’]
retstat = p.maybe(T(';')) + p.maybe(explist) + T('return') >> node('retstat')


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

# XXX: parsing of statements is broken, don't use it!

local_var = explist + p.maybe(T('=') + namelist) + T('local') >> node("local-var")

assignment = explist + T('=') + varlist >> node("assignment")

local_function = funcbody + Name + T('function') + T('local') >> node("local-function")

function = funcbody + funcname + T('function') >> node("function")

for_in_loop = T('end') + block + T('do') + explist + T('in') + namelist + T('for') >> node("for-in-loop")

for_loop = (
    T('end') + block + T('do') +
    p.maybe(exp + T(',')) + exp + T(',') + exp + T('=') + Name + T('for')
) >> node("for-loop")

if_then_else = (
    T('end') +
    p.maybe(block + T('else')) +
    p.many(block + T('then') + exp + T('elseif')) +
    block + T('then') + exp + T('if')
) >> node('if-then-else')

repeat_until = exp + T('until') + block + T('repeat') >> node('repeat-until')

while_loop = T('end') + block + T('do') + exp + T('while') >> node('while-loop')

do_block = T('end') + block + T('do') >> node('do-block')

goto_statement = Name + T('goto') >> node('goto')

stat = (
    local_var |
    assignment |
    local_function |
    function |
    for_in_loop |
    for_loop |
    if_then_else |
    repeat_until |
    while_loop |
    do_block |
    goto_statement |
    T('break') |
    label |
    functioncall |
    T(';')
) >> node('stat')


# block ::= {stat} [retstat]
block.define(
    p.maybe(retstat) + p.many(stat) >> node('block')
)

# chunk
chunk = block + p.finished

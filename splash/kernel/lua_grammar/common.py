# -*- coding: utf-8 -*-
"""
Common utilities and definitions for Lua parsing.
"""
from __future__ import absolute_import
from operator import attrgetter
from funcparserlib import parser as p


token_value = attrgetter("value")

def T(val):
    if isinstance(val, set):
        return p.some(lambda t: t.value in val) >> token_value
    else:
        return p.some(lambda t: t.value == val) >> token_value


Name = p.some(lambda t: t.type == 'iden') >> token_value
String = p.some(lambda t: t.type == 'string') >> token_value
Number = p.some(lambda t: t.type == 'number') >> token_value


class Node(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __repr__(self):
        return "%s:%r" % (self.name, self.value)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            return "Node({name!r}, ...)".format(name=self.name)

        if isinstance(self.value, (list, tuple)):
            with p.group(2, 'Node({name!r}, ['.format(name=self.name), '])'):
                p.breakable()
                for idx, v in enumerate(self.value):
                    if idx:
                        p.text(",")
                        p.breakable()
                    p.pretty(v)
        else:
            p.text('Node({name!r}, '.format(name=self.name))
            p.pretty(self.value)
            p.breakable()
            p.text(')')


def node(name):
    return lambda value: Node(name, value)


# ======================= Common grammar parts =============================

# unop ::= ‘-’ | not | ‘#’
unop = T({'-', 'not', '#'})


# binop ::= ‘+’ | ‘-’ | ‘*’ | ‘/’ | ‘^’ | ‘%’ | ‘..’ |
#           ‘<’ | ‘<=’ | ‘>’ | ‘>=’ | ‘==’ | ‘~=’ |
#           and | or
binop = T(set("+-*/^%><") | {"..", "==", "~=", ">=", "<=", "and", "or"})


# fieldsep ::= ‘,’ | ‘;’
fieldsep = T({',', ';'})

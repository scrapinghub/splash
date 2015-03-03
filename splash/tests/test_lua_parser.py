# -*- coding: utf-8 -*-
""" Unit tests for Lua parser internals """
from __future__ import absolute_import
import functools

import pytest
lupa = pytest.importorskip("lupa")

from splash.kernel.lua_parser import (
    Standalone,
    ObjectAttribute,
    ObjectMethod,
    ObjectAttributeIndexed,
    ObjectIndexedComplete,
    ConstantMethod,
    SplashMethod,
    SplashMethodOpenBrace,
    SplashAttribute,
)
from .test_completer import code_and_cursor_pos


def _parse(completer, code):
    """ Parse the code. """
    code, cursor_pos = code_and_cursor_pos(code)
    return completer.parse(code, cursor_pos)


@pytest.fixture()
def parse(completer):
    return functools.partial(_parse, completer)


@pytest.fixture()
def inspect_parse(inspector):
    return functools.partial(_parse, inspector)


@pytest.mark.parametrize(["code", "result"], [
    # standalone identifiers
    ["foo", Standalone("foo")],
    ["hello foo", Standalone("foo")],

    # object attribute access
    ["hello.foo", ObjectAttribute(["foo", "hello"])],
    ["foo.egg.spam", ObjectAttribute(["spam", "egg", "foo"])],
    ["foo.egg.", ObjectAttribute(["", "egg", "foo"])],
    ["foo.", ObjectAttribute(["", "foo"])],
    [".", None],
    [".foo", None],
    [".foo.bar", None],
    ["foo['egg'].spam", ObjectAttribute(["spam", "egg", "foo"])],
    ["foo[0].spam", ObjectAttribute(["spam", 0, "foo"])],
    ["['foo']['egg'].spam", None],
    ["go:['foo']['egg'].spam", None],
    ["go:['foo']['egg'].spam", None],

    # method calls using : syntax
    ["foo:go", ObjectMethod(["go", "foo"])],
    ["foo:", ObjectMethod(["", "foo"])],
    ["foo.bar:go", ObjectMethod(["go", "bar", "foo"])],
    ["foo['bar']:go", ObjectMethod(["go", "bar", "foo"])],
    ["['bar']:go", None],

    # unfinished ["foo  lookups
    ["foo['", ObjectAttributeIndexed(["", "'", "foo"])],
    ["foo['go", ObjectAttributeIndexed(["go", "'", "foo"])],
    ["foo['bar']['go", ObjectAttributeIndexed(["go", "'", "bar", "foo"])],
    ["foo.bar['go", ObjectAttributeIndexed(["go", "'", "bar", "foo"])],
    pytest.mark.xfail(["foo.bar:['go", None]),  # parsed as "Standalone"
    pytest.mark.xfail(["x.['go", None]),
    pytest.mark.xfail(["['go", None]),

    # finished ["foo"] lookups
    ["foo['go']", ObjectIndexedComplete(["go", "foo"])],
    ["bar.foo['go']", ObjectIndexedComplete(["go", "foo", "bar"])],
    ["foo[5]", ObjectIndexedComplete([5, "foo"])],

    # constants
    ["('hello'", None],
    ["('hello')", None],
    ["('hello'):", ConstantMethod(["", "hello"])],
    ["('hello'):fo", ConstantMethod(["fo", "hello"])],
    ["'hello':fo", None],
    ["('hello'):", ConstantMethod(["", "hello"])],
    ["(42):fo", ConstantMethod(["fo", 42])],
    ["42:fo", None],

    # empty
    ["(", None],
    [".", None],
    ["", None],
    ["  ", None],
    ["45.", None],
    ["45", None],

    # splash-specific parsing
    ["splash:", SplashMethod(["", "splash"])],
    ["splash:x", SplashMethod(["x", "splash"])],
    ["splash:x(", SplashMethodOpenBrace(["x", "splash"])],
    ["splash:x{", SplashMethodOpenBrace(["x", "splash"])],
    ["splash:x {", SplashMethodOpenBrace(["x", "splash"])],
    ["splash:meth{foo=bar,", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{foo=bar, |x=5}", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{foo=bar,baz=5,", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{foo=bar,", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{['foo']='bar',", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{[1]='bar', ", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{'bar',", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{'bar',baz=2.1,", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{baz=false,", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{baz=2+3,", SplashMethodOpenBrace(["meth", "splash"])],
    ["splash:meth{baz=#foo,", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo()]=func(2+3),", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo.bar()]=func.munc(2+3),", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo['bar']()]=func['munc'](2+3),", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo:bar()]=func:munc(2+3),", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo()]=func(-2+3),", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo()]=func(2+3)*2,", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo()*2]=func(2+3)*2,", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo 'x']=func{x=1},", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo.bar 'x']=func{x=1},", SplashMethodOpenBrace(["meth", "splash"])],
    # ["splash:meth{[foo 5]=func 'bar',", SplashMethodOpenBrace(["meth", "splash"])],

    ["splash:{", None],
    ["splash.foo:x", ObjectMethod(["x", "foo", "splash"])],
    ["foo.splash:x", ObjectMethod(["x", "splash", "foo"])],
    ["splash.", SplashAttribute(["", "splash"])],
    ["splash.x", SplashAttribute(["x", "splash"])],
    ["splash.foo.x", ObjectAttribute(["x", "foo", "splash"])],
    ["foo.splash.x", ObjectAttribute(["x", "splash", "foo"])],

])
def test_inspect(inspect_parse, code, result):
    assert inspect_parse(code) == result


def test_splash_attr(parse):
    m = parse("splash.at")
    assert m.prefix == "at"
    assert m.names_chain == ["splash"]

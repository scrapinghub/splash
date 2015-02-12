# -*- coding: utf-8 -*-
from __future__ import absolute_import

import pytest
lupa = pytest.importorskip("lupa")

from splash.kernel.completer import Tok


def autocomplete(completer, code):
    """
    Ask completer to complete the ``code``;
    cursor position is specified by | symbol.
    """
    cursor_pos = code.index("|")
    code = code.replace("|", "")
    res = completer.complete(code, cursor_pos)
    assert res["status"] == "ok"
    assert res["cursor_end"] == cursor_pos
    return res


def test_tokenize(completer):
    code = """
    function foo()
        local x = 1.
        local y = [[hello]]
    end
    """
    assert completer.tokenize(code) == [
        Tok(type=u'space', value=u'\n    '),
        Tok(type=u'keyword', value=u'function'),
        Tok(type=u'space', value=u' '),
        Tok(type=u'iden', value=u'foo'),
        Tok(type=u'(', value=u'('),
        Tok(type=u')', value=u')'),
        Tok(type=u'space', value=u'\n        '),
        Tok(type=u'keyword', value=u'local'),
        Tok(type=u'space', value=u' '),
        Tok(type=u'iden', value=u'x'),
        Tok(type=u'space', value=u' '),
        Tok(type=u'=', value=u'='),
        Tok(type=u'space', value=u' '),
        Tok(type=u'number', value=1),
        Tok(type=u'space', value=u'\n        '),
        Tok(type=u'keyword', value=u'local'),
        Tok(type=u'space', value=u' '),
        Tok(type=u'iden', value=u'y'),
        Tok(type=u'space', value=u' '),
        Tok(type=u'=', value=u'='),
        Tok(type=u'space', value=u' '),
        Tok(type=u'string', value=u'hello'),
        Tok(type=u'space', value=u'\n    '),
        Tok(type=u'keyword', value=u'end'),
        Tok(type=u'space', value=u'\n    ')
    ]


def test_complete_keywords(completer):
    res = autocomplete(completer, "fun|")
    assert "function" in res["matches"]

    res = autocomplete(completer, "while t| do")
    assert "true" in res["matches"]


def test_dont_complete_keywords_as_attributes(completer):
    res = autocomplete(completer, "x.fun|")
    assert "function" not in res["matches"]

    res = autocomplete(completer, "x:fun|")
    assert "function" not in res["matches"]


def test_complete_globals(completer):
    res = autocomplete(completer, "x = tab|")
    assert "table" in res["matches"]

    res = autocomplete(completer, "x = s|")
    assert "string" in res["matches"]
    assert "select" in res["matches"]
    assert "spoon" not in res["matches"]
    assert all(m.startswith("s") for m in res["matches"])


def test_complete_user_globals(completer):
    completer.lua.execute("spoon = 5")
    res = autocomplete(completer, "x = s|")
    assert "string" in res["matches"]
    assert "select" in res["matches"]
    assert "spoon" in res["matches"]


def test_dont_complete_globals_as_attributes(completer):
    res = autocomplete(completer, "foo = x.s|")
    assert "string" not in res["matches"]


def test_no_completions_on_nothing(completer):
    res = autocomplete(completer, "|")
    assert res["matches"] == []

    res = autocomplete(completer, " | ")
    assert res["matches"] == []


def test_globals_attributes(completer):
    res = autocomplete(completer, "foo = string.|")
    assert {'len', 'lower', 'reverse', 'upper'} <= set(res["matches"])
    assert 'concat' not in res["matches"]

    res = autocomplete(completer, "foo = string.l|")
    assert res["matches"] == ["len", "lower"]


def test_complete_methods(completer):
    completer.lua.execute("""
    tbl = {foo="bar"}
    function tbl:hello()
        return 123
    end
    """)
    res = autocomplete(completer, "tbl:|")
    assert res["matches"] == ["hello"]     # fixme: metamethods?

    res = autocomplete(completer, "tbl.|")
    assert res["matches"] == ["foo", "hello"]


def test_complete_local_variables(completer):
    res = autocomplete(completer, """
    status = "statue"
    stats = "sterling"
    x = st|
    """)
    assert res["matches"] == ["stats", "status", "string"]


def test_complete_latter_local_variables(completer):
    res = autocomplete(completer, """
    x = st|
    status = "statue"
    stats = "sterling"
    """)
    assert res["matches"] == ["stats", "status", "string"]


@pytest.mark.xfail
def test_dont_complete_globals_inside_string(completer):
    res = autocomplete(completer, "x = 's|'")
    assert "string" not in res["matches"]


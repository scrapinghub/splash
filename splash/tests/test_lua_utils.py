# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest
import pytest

from splash.lua import (
    table_as_kwargs,
    table_as_kwargs_method,
    lua2python,
    python2lua
)


@table_as_kwargs
def func_1(x):
    return ("x=%s" % (x, ))


@table_as_kwargs
def func_2(x, y):
    return ("x=%s, y=%s" % (x, y))


@table_as_kwargs
def func_3(x, y, z='default'):
    return ("x=%s, y=%s, z=%s" % (x, y, z))


class MyCls_1(object):
    @table_as_kwargs_method
    def meth(self, x):
        return ("x=%s" % (x,))


class MyCls_2(object):
    @table_as_kwargs_method
    def meth(self, x, y):
        return ("x=%s, y=%s" % (x, y))


class MyCls_3(object):
    @table_as_kwargs_method
    def meth(self, x, y, z='default'):
        return ("x=%s, y=%s, z=%s" % (x, y, z))


@pytest.mark.usefixtures("lua")
class KwargsDecoratorTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(KwargsDecoratorTest, self).__init__(*args, **kwargs)
        self.arg1 = func_1
        self.arg2 = func_2
        self.arg3 = func_3

    def assertResult(self, f, call_txt, res_txt):
        lua_func = self.lua.eval("function (f) return f%s end" % call_txt)
        assert lua_func(f) == res_txt

    def assertIncorrect(self, f, call_txt):
        lua_func = self.lua.eval("function (f) return f%s end" % call_txt)
        with pytest.raises(TypeError):
            lua_func(f)

    def test_many_args(self):
        self.assertResult(self.arg2, "{x=1, y=2}", "x=1, y=2")
        self.assertResult(self.arg2, "{x=2, y=1}", "x=2, y=1")
        self.assertResult(self.arg2, "{y=1, x=2}", "x=2, y=1")
        self.assertResult(self.arg2, "(1, 2)",     "x=1, y=2")

    def test_single_arg(self):
        self.assertResult(self.arg1, "{x=1}", "x=1")
        self.assertResult(self.arg1, "(1)", "x=1")
        self.assertResult(self.arg1, "(nil)", "x=None")

    def test_defaults(self):
        self.assertResult(self.arg3, "{x=1, y=2}", "x=1, y=2, z=default")
        self.assertResult(self.arg3, "{x=1, y=2, z=3}", "x=1, y=2, z=3")

    def test_defaults_incorrect(self):
        self.assertIncorrect(self.arg3, "{x=1, z=3}")

    def test_kwargs_unknown(self):
        self.assertIncorrect(self.arg2, "{x=1, y=2, z=3}")
        self.assertIncorrect(self.arg2, "{y=2, z=3}")
        self.assertIncorrect(self.arg1, "{x=1, y=2}")

    def test_posargs_bad(self):
        self.assertIncorrect(self.arg1, "(1,2)")
        self.assertIncorrect(self.arg1, "()")

    def test_posargs_kwargs(self):
        self.assertResult(self.arg2, "{5, y=6}", "x=5, y=6")
        self.assertResult(self.arg2, "{y=6, 5}", "x=5, y=6")

        self.assertResult(self.arg3, "{x=5, y=6, z=8}", "x=5, y=6, z=8")
        self.assertResult(self.arg3, "{5, y=6, z=8}", "x=5, y=6, z=8")
        self.assertResult(self.arg3, "{5, y=6}", "x=5, y=6, z=default")
        self.assertResult(self.arg3, "{5, 6}", "x=5, y=6, z=default")
        self.assertResult(self.arg3, "{5, 6, 7}", "x=5, y=6, z=7")
        self.assertResult(self.arg3, "{z=7, 5, 6}", "x=5, y=6, z=7")

    def test_posargs_kwargs_nil(self):
        self.assertResult(self.arg3, "{5, nil, 6}", "x=5, y=None, z=6")
        self.assertResult(self.arg3, "{nil, nil, 6}", "x=None, y=None, z=6")
        # self.assertResult(self.arg3, "{nil, y=nil, z=6}", "x=None, y=None, z=6")
        # self.assertResult(self.arg3, "{x=nil, y=nil}", "x=None, y=None, z=default")

    def test_posargs_kwargs_bad(self):
        self.assertIncorrect(self.arg2, "{5, y=6, z=7}")

        self.assertIncorrect(self.arg3, "{5, z=7}")
        self.assertIncorrect(self.arg3, "{5}")


class MethodKwargsDecoratorTest(KwargsDecoratorTest):

    def __init__(self, *args, **kwargs):
        super(MethodKwargsDecoratorTest, self).__init__(*args, **kwargs)
        self.arg1 = MyCls_1()
        self.arg2 = MyCls_2()
        self.arg3 = MyCls_3()

    def assertResult(self, f, call_txt, res_txt):
        lua_func = self.lua.eval("function (obj) return obj:meth%s end" % call_txt)
        assert lua_func(f) == res_txt

    def assertIncorrect(self, f, call_txt):
        lua_func = self.lua.eval("function (obj) return obj:meth%s end" % call_txt)
        with pytest.raises(TypeError):
            lua_func(f)


@pytest.mark.usefixtures("lua")
class LuaPythonConversionTest(unittest.TestCase):

    def assertSurvivesConversion(self, obj):
        lua_obj = python2lua(self.lua, obj)
        py_obj = lua2python(self.lua, lua_obj)
        self.assertEqual(obj, py_obj)

    def test_numbers(self):
        self.assertSurvivesConversion(5)
        self.assertSurvivesConversion(0)
        self.assertSurvivesConversion(-3.14)

    def test_strings(self):
        self.assertSurvivesConversion("foo")
        self.assertSurvivesConversion("")

    @pytest.mark.xfail
    def test_unicode(self):
        # Does it fail because python2lua and lua2python assume
        # LuaRuntime is in play?
        self.assertSurvivesConversion(u"привет")

    def test_dict(self):
        self.assertSurvivesConversion({'x': 2, 'y': 3})

    def test_dict_empty(self):
        self.assertSurvivesConversion({})

    def test_dict_int_keys(self):
        self.assertSurvivesConversion({1: 'foo', 2: 'bar'})

    def test_dict_pyobject_key(self):
        key = object()
        self.assertSurvivesConversion({key: 'foo', 2: 'bar'})

    def test_dict_pyobject_value(self):
        value = object()
        self.assertSurvivesConversion({'foo': value, 'bar': 'bar'})

    def test_dict_recursive(self):
        dct = {}
        dct["x"] = dct
        with pytest.raises(ValueError):
            python2lua(self.lua, dct)

    def test_object(self):
        self.assertSurvivesConversion(object())

    def test_none(self):
        self.assertSurvivesConversion(None)

    @pytest.mark.xfail
    def test_none_values(self):
        self.assertSurvivesConversion({"foo": None})

    def test_list(self):
        self.assertSurvivesConversion(["foo", "bar"])

    def test_list_empty(self):
        self.assertSurvivesConversion([])

    def test_list_recursive(self):
        lst = []
        lst.append(lst)
        with pytest.raises(ValueError):
            python2lua(self.lua, lst)

    def test_list_nested(self):
        self.assertSurvivesConversion(["foo", "bar", [1, 2, "3", 10], [], [{}]])

    @pytest.mark.xfail
    def test_list_endswith_none(self):
        # FIXME
        self.assertSurvivesConversion([1, None])
        self.assertSurvivesConversion([None])

    def test_list_with_none(self):
        self.assertSurvivesConversion(["foo", None, 2])
        self.assertSurvivesConversion(["foo", None, None, 2])
        self.assertSurvivesConversion([None, "foo", None, 2])
        self.assertSurvivesConversion([None, None, None, 2])

    def test_list_like_tables(self):
        # List-like tables are still returned as dicts;
        # only tables which were lists originally are lists.
        tbl = self.lua.eval("{5, 6}")
        self.assertEqual(
            lua2python(self.lua, tbl),
            {1: 5, 2: 6}
        )

    def test_list_modified_incorrect(self):
        func = self.lua.eval("""
        function (arr)
           arr["foo"] = "bar"
           return arr
        end
        """)
        arr = python2lua(self.lua, [3, 4])
        arr2 = func(arr)
        with pytest.raises(ValueError):
            lua2python(self.lua, arr2)

    def test_list_modified_correct(self):
        func = self.lua.eval("""
        function (arr)
           table.insert(arr, "bar")
           return arr
        end
        """)
        arr = python2lua(self.lua, [3, 4])
        arr2 = func(arr)
        self.assertEqual(lua2python(self.lua, arr2), [3, 4, "bar"])

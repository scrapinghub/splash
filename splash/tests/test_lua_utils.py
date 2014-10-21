# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest
import pytest

from splash.lua import table_as_kwargs, table_as_kwargs_method


@table_as_kwargs
def func_1(x):
    return ("x=%s" % (x, ))


@table_as_kwargs
def func_2(x, y):
    return ("x=%s, y=%s" % (x, y))


class MyCls_1(object):
    @table_as_kwargs_method
    def meth(self, x):
        return ("x=%s" % (x,))


class MyCls_2(object):
    @table_as_kwargs_method
    def meth(self, x, y):
        return ("x=%s, y=%s" % (x, y))


@pytest.mark.usefixtures("lua")
class KwargsDecoratorTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(KwargsDecoratorTest, self).__init__(*args, **kwargs)
        self.arg1 = func_1
        self.arg2 = func_2

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

    def test_kwargs_unknown(self):
        self.assertIncorrect(self.arg2, "{x=1, y=2, z=3}")
        self.assertIncorrect(self.arg2, "{y=2, z=3}")
        self.assertIncorrect(self.arg1, "{x=1, y=2}")

    def test_posargs_bad(self):
        self.assertIncorrect(self.arg1, "(1,2)")
        self.assertIncorrect(self.arg1, "()")


class MethodKwargsDecoratorTest(KwargsDecoratorTest):

    def __init__(self, *args, **kwargs):
        super(MethodKwargsDecoratorTest, self).__init__(*args, **kwargs)
        self.arg1 = MyCls_1()
        self.arg2 = MyCls_2()

    def assertResult(self, f, call_txt, res_txt):
        lua_func = self.lua.eval("function (obj) return obj:meth%s end" % call_txt)
        assert lua_func(f) == res_txt

    def assertIncorrect(self, f, call_txt):
        lua_func = self.lua.eval("function (obj) return obj:meth%s end" % call_txt)
        with pytest.raises(TypeError):
            lua_func(f)

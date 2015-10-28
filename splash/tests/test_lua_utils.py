# -*- coding: utf-8 -*-
from __future__ import absolute_import
import unittest
import pytest
lupa = pytest.importorskip("lupa")

from splash.lua import lua2python, python2lua


@pytest.mark.usefixtures("lua")
class LuaPythonConversionTest(unittest.TestCase):

    def assertSurvivesConversion(self, obj, encoding='utf8'):
        lua_obj = python2lua(self.lua, obj, encoding=encoding)
        py_obj = lua2python(self.lua, lua_obj, encoding=encoding)
        self.assertEqual(obj, py_obj)
        self.assertEqual(obj.__class__, py_obj.__class__)

    def test_numbers(self):
        self.assertSurvivesConversion(5)
        self.assertSurvivesConversion(0)
        self.assertSurvivesConversion(-3.14)

    def test_unicode_strings(self):
        self.assertSurvivesConversion(u"foo")
        self.assertSurvivesConversion(u"")

    def test_byte_strings(self):
        self.assertSurvivesConversion(b"foo", encoding=None)
        self.assertSurvivesConversion(b"", encoding=None)

    def test_unicode_nonascii(self):
        self.assertSurvivesConversion(u"привет")

    def test_dict(self):
        self.assertSurvivesConversion({b'x': 2, b'y': 3}, encoding=None)
        self.assertSurvivesConversion({'x': 2, 'y': 3})

    def test_dict_empty(self):
        self.assertSurvivesConversion({})

    def test_dict_int_keys(self):
        self.assertSurvivesConversion({1: b'foo', 2: b'bar'}, encoding=None)
        self.assertSurvivesConversion({1: 'foo', 2: 'bar'})

    def test_dict_pyobject_key(self):
        key = object()
        self.assertSurvivesConversion({key: b'foo', 2: b'bar'}, encoding=None)
        self.assertSurvivesConversion({key: 'foo', 2: 'bar'}, encoding='utf8')

    def test_dict_pyobject_value(self):
        value = object()
        self.assertSurvivesConversion({b'foo': value, b'bar': b'bar'}, encoding=None)
        self.assertSurvivesConversion({'foo': value, 'bar': 'bar'}, encoding='utf8')

    def test_dict_recursive(self):
        dct = {}
        dct["x"] = dct
        with pytest.raises(ValueError):
            python2lua(self.lua, dct)

    def test_lua_table_in_python_container(self):
        dct = {
            "foo": "foo",
            "bar": self.lua.table_from({"egg": "spam"}),
            "baz": [self.lua.table_from({"foo": "bar"})],
        }
        value = lua2python(self.lua, dct)
        self.assertEqual(value, {
            "foo": "foo",
            "bar": {"egg": "spam"},
            "baz": [{"foo": "bar"}],
        })

    def test_object(self):
        self.assertSurvivesConversion(object())

    def test_none(self):
        self.assertSurvivesConversion(None)

    @pytest.mark.xfail
    def test_none_values(self):
        self.assertSurvivesConversion({"foo": None})

    def test_list(self):
        self.assertSurvivesConversion([b"foo", b"bar"], encoding=None)
        self.assertSurvivesConversion(["foo", "bar"], encoding='utf8')

    def test_list_empty(self):
        self.assertSurvivesConversion([])

    def test_list_recursive(self):
        lst = []
        lst.append(lst)
        with pytest.raises(ValueError):
            python2lua(self.lua, lst)

    def test_list_nested(self):
        self.assertSurvivesConversion(
            [b"foo", b"bar", [1, 2, b"3", 10], [], [{}]],
            encoding=None
        )
        self.assertSurvivesConversion(
            ["foo", "bar", [1, 2, "3", 10], [], [{}]],
            encoding='utf8'
        )

    @pytest.mark.xfail
    def test_list_endswith_none(self):
        # FIXME
        self.assertSurvivesConversion([1, None])
        self.assertSurvivesConversion([None])

    def test_list_with_none(self):
        self.assertSurvivesConversion([b"foo", None, 2], encoding=None)
        self.assertSurvivesConversion([b"foo", None, None, 2], encoding=None)
        self.assertSurvivesConversion([None, b"foo", None, 2], encoding=None)
        self.assertSurvivesConversion([None, None, None, 2], encoding=None)

        self.assertSurvivesConversion(["foo", None, 2], encoding='utf8')
        self.assertSurvivesConversion(["foo", None, None, 2], encoding='utf8')
        self.assertSurvivesConversion([None, "foo", None, 2], encoding='utf8')
        self.assertSurvivesConversion([None, None, None, 2], encoding='utf8')

    def test_sparse_list(self):
        func1 = self.lua.eval("""
        function (arr)
            arr[5] = "foo"
            return arr
        end
        """)
        func2 = self.lua.eval("""
        function (arr)
            arr[100000] = "foo"
            return arr
        end
        """)
        arr = python2lua(self.lua, [1, 2])
        arr1 = lua2python(self.lua, func1(arr))
        self.assertEqual(arr1, [1, 2, None, None, "foo"])

        with pytest.raises(ValueError):
            arr2 = lua2python(self.lua, func2(arr))

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
        arr = python2lua(self.lua, [3, 4],)
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

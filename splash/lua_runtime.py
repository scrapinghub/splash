# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import weakref
import contextlib

from splash.lua import lua2python, python2lua, get_new_runtime


class SplashLuaRuntime(object):
    """
    Lua runtime wrapper, optionally with a sandbox.
    """
    def __init__(self, sandboxed, lua_package_path, lua_sandbox_allowed_modules):
        """
        :param bool sandboxed: whether the runtime should be sandboxed
        :param str lua_package_path: paths to add to Lua package.path
        :param iterable lua_sandbox_allowed_modules: a list of modules allowed
            to be required from a sandbox
        """
        self._sandboxed = sandboxed
        self._lua = self._create_runtime(lua_package_path)
        self._setup_lua_sandbox(lua_sandbox_allowed_modules)
        self._allowed_object_attrs = weakref.WeakKeyDictionary()

    def add_to_globals(self, name, value):
        code = "function(%s_) %s = %s_ end" % (name, name, name)
        self.eval(code)(value)

    def table_from(self, *args, **kwargs):
        return self._lua.table_from(*args, **kwargs)

    def eval(self, *args, **kwargs):
        return self._lua.eval(*args, **kwargs)

    def execute(self, *args, **kwargs):
        return self._lua.execute(*args, **kwargs)

    def globals(self, *args, **kwargs):
        return self._lua.globals(*args, **kwargs)

    def add_allowed_object(self, obj, attr_whitelist):
        """ Add a Python object to a list of objects the runtime can access """
        self._allowed_object_attrs[obj] = attr_whitelist

    def remove_allowed_object(self, obj):
        """ Remove an object from a list of objects the runtime can access """
        if obj in self._allowed_object_attrs:
            del self._allowed_object_attrs[obj]

    @contextlib.contextmanager
    def object_allowed(self, obj, attr_whitelist):
        """ Temporarily enable an access to a Python object """
        self.add_allowed_object(obj, attr_whitelist)
        try:
            yield
        finally:
            self.remove_allowed_object(obj)

    def lua2python(self, *args, **kwargs):
        kwargs.setdefault("binary", True)
        kwargs.setdefault("strict", True)
        return lua2python(self._lua, *args, **kwargs)

    def python2lua(self, *args, **kwargs):
        return python2lua(self._lua, *args, **kwargs)

    def instruction_count(self):
        if not self._sandboxed:
            return -1
        try:
            return self._sandbox.instruction_count
        except Exception as e:
            print(e)
            return -1

    def create_coroutine(self, func):
        """
        Return a Python object which starts a coroutine when called.
        """
        if self._sandboxed:
            return self._sandbox.create_coroutine(func)
        else:
            return func.coroutine

    def _create_runtime(self, lua_package_path):
        """
        Return a restricted Lua runtime.
        Currently it only allows accessing attributes of this object.
        """
        attribute_handlers = (self._attr_getter, self._attr_setter)
        runtime = get_new_runtime(attribute_handlers=attribute_handlers)
        self._setup_lua_paths(runtime, lua_package_path)
        return runtime

    def _setup_lua_paths(self, lua, lua_package_path):
        default_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                'lua_modules'
            )
        ) + "/?.lua"
        if lua_package_path:
            packages_path = ";".join([default_path, lua_package_path])
        else:
            packages_path = default_path

        lua.execute("""
        package.path = "{packages_path};" .. package.path
        """.format(packages_path=packages_path))

    @property
    def _sandbox(self):
        return self.eval("require('sandbox')")

    def _setup_lua_sandbox(self, allowed_modules):
        self._sandbox["allowed_require_names"] = self.python2lua(
            {name: True for name in allowed_modules}
        )

    def _attr_getter(self, obj, attr_name):

        if not isinstance(attr_name, basestring):
            raise AttributeError("Non-string lookups are not allowed (requested: %r)" % attr_name)

        if isinstance(attr_name, basestring) and attr_name.startswith("_"):
            raise AttributeError("Access to private attribute %r is not allowed" % attr_name)

        if obj not in self._allowed_object_attrs:
            raise AttributeError("Access to object %r is not allowed" % obj)

        if attr_name not in self._allowed_object_attrs[obj]:
            raise AttributeError("Access to private attribute %r is not allowed" % attr_name)

        value = getattr(obj, attr_name)
        return value

    def _attr_setter(self, obj, attr_name, value):
        raise AttributeError("Direct writing to Python objects is not allowed")

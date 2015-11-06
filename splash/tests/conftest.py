# -*- coding: utf-8 -*-
from __future__ import absolute_import

import pytest
from .utils import TestServers, SplashServer


@pytest.yield_fixture(scope="session")
def test_servers():
    with TestServers() as ts:
        yield ts


@pytest.yield_fixture(scope="class")
def class_ts(request, test_servers):
    """ Splash server and mockserver """
    request.cls.ts = test_servers
    yield test_servers


@pytest.yield_fixture(scope="session")
def splash_unrestricted():
    with SplashServer(extra_args=['--disable-lua-sandbox']) as splash:
        yield splash


@pytest.yield_fixture(scope="class")
def class_splash_unrestricted(request, splash_unrestricted):
    """ Non-sandboxed Splash server """
    request.cls.splash_unrestricted = splash_unrestricted
    yield splash_unrestricted


@pytest.fixture()
def lua(request):
    import lupa
    lua = lupa.LuaRuntime(encoding=None)
    request.cls.lua = lua
    return lua


@pytest.fixture()
def configured_lua():
    from splash.lua_runtime import SplashLuaRuntime
    return SplashLuaRuntime(
        sandboxed=False,
        lua_package_path="",
        lua_sandbox_allowed_modules=()
    )


@pytest.fixture()
def completer(configured_lua):
    from splash.kernel.completer import Completer
    return Completer(configured_lua)


@pytest.fixture()
def lua_lexer(configured_lua):
    from splash.kernel.lua_parser import LuaLexer
    return LuaLexer(configured_lua)


@pytest.fixture()
def inspector(configured_lua):
    from splash.kernel.inspections import Inspector
    return Inspector(configured_lua)

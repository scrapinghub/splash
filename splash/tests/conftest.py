# -*- coding: utf-8 -*-
from __future__ import absolute_import

import pytest
from .utils import TestServers


@pytest.yield_fixture(scope="session")
def test_servers():
    with TestServers() as ts:
        yield ts
        ts.print_output()


@pytest.yield_fixture(scope="class")
def class_ts(request, test_servers):
    """ Splash server and mockserver """
    request.cls.ts = test_servers
    yield test_servers
    test_servers.print_output()


@pytest.fixture()
def print_ts_output(class_ts):
    class_ts.print_output()

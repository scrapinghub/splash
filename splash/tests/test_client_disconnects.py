# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import random
import unittest
import time
import six
from six.moves.http_client import HTTPConnection

import pytest
lupa = pytest.importorskip("lupa")


@pytest.mark.usefixtures("class_splash_unrestricted")
class StopProcessingTest(unittest.TestCase):
    """
    These tests check that script is stopped after connection
    is closed.

    We can't use splash:http_get or XmlHTTPRequest because
    they don't work when page is stopped, and there is no other
    way to communicate with outside world in sandboxed Splash,
    so a non-sandboxed version is started.
    """
    CREATE_FILE = """
    function create_file(filename, contents)
        fp = io.open(filename, "w")
        fp:write(contents)
        fp:close()
    end
    """

    def get_random_filename(self):
        tempdir = self.splash_unrestricted.tempdir
        return os.path.join(tempdir, str(random.random()))

    def open_http_connection(self, code, query=None, method='GET'):
        """
        Send a request to non-sandboxed Splash, return an HTTPConnection.
        create_file Lua function is pre-loaded.
        """
        q = {"lua_source": self.CREATE_FILE + "\n" + code}
        q.update(query or {})
        conn = HTTPConnection('localhost', self.splash_unrestricted.portnum)
        conn.request(method, "/execute/?" + six.moves.urllib.parse.urlencode(q))
        return conn

    def test_wait_timer_stopped_after_request_finished(self):
        filename = self.get_random_filename()
        conn = self.open_http_connection("""
        function main(splash)
            splash:wait(1.0)
            create_file(splash.args.filename, "not empty")
            return "ok"
        end
        """, {'filename': filename})
        time.sleep(0.1)
        assert not os.path.exists(filename)  # not yet created

        # XXX: why can't we use requests or urllib, why
        # don't they close a connection after a timeout error?
        conn.close()

        time.sleep(2)
        assert not os.path.exists(filename)  # script is aborted

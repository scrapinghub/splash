#!/usr/bin/env python

"""Simple static file server."""

import argparse
import os
import subprocess
import time
import sys
import logging
from contextlib import contextmanager

from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.static import File
from twisted.python.log import startLogging

import requests

parser = argparse.ArgumentParser("")
parser.add_argument('--port', type=int, default=8806)
parser.add_argument('--path', help='Path to be served', default='.')
parser.add_argument('--logfile', default=sys.stderr,
                    type=argparse.FileType(mode='w'),
                    help='File to write logs to')


class FileServerSubprocess(object):
    logger = logging.getLogger('file_server')

    """Serve files from specified directory statically in a subprocess."""
    def __init__(self, port, path, logfile=None):
        self.port = port
        self.path = path
        self.logfile = logfile
        self.server = 'http://localhost:%d' % port

    def url(self, endpoint):
        return self.server + '/' + endpoint

    def __enter__(self):
        # command = ['twistd',
        #            '-n',    # don't daemonize
        #            'web',   # start web component
        #            '--port', str(int(port)),
        #            '--path', os.path.abspath(directory), ]
        # if logfile is not None:
        #     command += ['--logfile', logfile]
        command = ['python', __file__,
                   '--port', str(int(self.port)),
                   '--path', os.path.abspath(self.path)]
        if self.logfile is not None:
            command += ['--logfile', self.logfile]
        self.logger.info("Starting file server subprocess: %s", command)
        self._site_server = subprocess.Popen(command)
        # It might take some time to bring up the server, wait for up to 10s.
        for i in xrange(100):
            try:
                self.logger.info("Checking if file server is active")
                requests.get(self.url(''))
                break
            except requests.ConnectionError:
                time.sleep(0.1)
        else:
            msg = "File server subprocess startup timed out"
            if self.logfile:
                with open(self.logfile, 'r') as log_f:
                    msg += ", logs:\n" + log_f.read()
            raise RuntimeError(msg)

    def __exit__(self, *args):
        self._site_server.kill()
        self._site_server.wait()


def main():
    args = parser.parse_args()
    startLogging(args.logfile)
    resource = File(os.path.abspath(args.path))
    site = Site(resource)
    reactor.listenTCP(args.port, site)
    reactor.run()


if __name__ == '__main__':
    main()

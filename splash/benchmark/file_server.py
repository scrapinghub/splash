#!/usr/bin/env python

"""Simple static file server."""

import argparse
import os
import subprocess
import time
import sys
from contextlib import contextmanager

from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.static import File
from twisted.python.log import startLogging

import requests

parser = argparse.ArgumentParser("")
parser.add_argument('--port', type=int, default=8806)
parser.add_argument('--directory', help='Directory to be served', default='.')
parser.add_argument('--logfile', default=sys.stderr, type=argparse.FileType(mode='w'), 
                    help='File to write logs to')

@contextmanager
def serve_files(port, directory, logfile=None):
    """Serve files from specified directory statically in a subprocess."""
    # command = ['twistd',
    #            '-n',    # don't daemonize
    #            'web',   # start web component
    #            '--port', str(int(port)),
    #            '--path', os.path.abspath(directory), ]
    # if logfile is not None:
    #     command += ['--logfile', logfile]
    command = ['python', __file__,
               '--port', str(int(port)),
               '--directory', os.path.abspath(directory)]
    if logfile is not None:
        command += ['--logfile', logfile]
    site_server = subprocess.Popen(command)
    try:
        # It might take some time to bring up the server, wait for up to 10s.
        for i in xrange(100):
            try:
                requests.get('http://localhost:%d' % port)
            except requests.ConnectionError:
                time.sleep(0.1)
            else:
                break
        yield
    finally:
        site_server.terminate()


def main():
    args = parser.parse_args()
    startLogging(args.logfile)
    resource = File(os.path.abspath(args.directory))
    site = Site(resource)
    reactor.listenTCP(args.port, site)
    reactor.run()


if __name__ == '__main__':
    main()

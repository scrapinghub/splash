#!/usr/bin/env python

"""
Simple static file server.
"""

import argparse
import os
import SimpleHTTPServer
import SocketServer
import subprocess
from contextlib import contextmanager


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('port', type=int, help='Port number to listen at')
parser.add_argument('directory', type=str, help='Directory to serve')


class ReusingTCPServer(SocketServer.TCPServer):
    allow_reuse_address = True


class RequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def address_string(self):
        return "fileserver"


@contextmanager
def serve_files(port, directory):
    """Serve files from current directory statically in a subprocess."""
    site_server = subprocess.Popen(['python', '-m', __name__,
                                    str(port), directory])
    try:
        yield
    finally:
        site_server.terminate()


if __name__ == '__main__':
    args = parser.parse_args()
    os.chdir(args.directory)
    server = ReusingTCPServer(("", args.port), RequestHandler)
    server.serve_forever()

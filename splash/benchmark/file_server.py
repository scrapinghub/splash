import SimpleHTTPServer
import SocketServer
import subprocess
import sys
from contextlib import contextmanager


class ReusingTCPServer(SocketServer.TCPServer):
    allow_reuse_address = True


class RequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def address_string(self):
        return "fileserver"


@contextmanager
def serve_files(port):
    """Serve files from current directory statically in a subprocess."""
    site_server = subprocess.Popen(['python', '-m', __name__,
                                    str(port)])
    try:
        yield
    finally:
        site_server.terminate()


if __name__ == '__main__':
    port = int(sys.argv[1])
    server = ReusingTCPServer(("", port), RequestHandler)
    server.serve_forever()

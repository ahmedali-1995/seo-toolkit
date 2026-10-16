"""Local preview: serves public/ and routes /api/<name> to api/<name>.py (stdlib only)."""
import importlib
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "api"))
sys.path.insert(0, ROOT)


class Dev(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=os.path.join(ROOT, "public"), **k)

    def _api(self, method):
        name = urlparse(self.path).path[len("/api/"):]
        try:
            h = importlib.import_module(name).handler
        except (ImportError, ValueError):
            self.send_error(404)
            return
        # Instantiate the function's handler class without running its socket-serving
        # __init__, then lend it this request's streams.
        fn = h.__new__(h)
        for attr in ("rfile", "wfile", "headers", "path", "request_version",
                     "command", "requestline", "client_address", "server"):
            setattr(fn, attr, getattr(self, attr))
        fn.close_connection = True
        getattr(fn, f"do_{method}")()

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api("GET")
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._api("POST")
        self.send_error(404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"http://127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), Dev).serve_forever()

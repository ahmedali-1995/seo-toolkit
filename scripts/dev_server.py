"""Local preview of the demo: python scripts/dev_server.py [port] (stdlib only)."""
import os
import sys
from wsgiref.simple_server import WSGIRequestHandler, make_server

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app import app  # noqa: E402


class Quiet(WSGIRequestHandler):
    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"http://127.0.0.1:{port}")
    make_server("127.0.0.1", port, app, handler_class=Quiet).serve_forever()

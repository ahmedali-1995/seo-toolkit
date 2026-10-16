"""Shared plumbing for the Vercel Python functions (files starting with _ are not routes)."""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

MAX_BODY = 300_000  # bytes; the demo is a showcase, not a processing service


class ApiError(Exception):
    pass


def make_handler(post=None, get=None):
    class handler(BaseHTTPRequestHandler):
        def _send(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _run(self, fn, *args):
            if fn is None:
                return self._send(405, {"error": "method not allowed"})
            try:
                self._send(200, fn(*args))
            except ApiError as e:
                self._send(400, {"error": str(e)})
            except Exception as e:  # never leak a traceback to the client
                self._send(500, {"error": f"{type(e).__name__}"})

        def do_GET(self):
            self._run(get, self.path)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, {"error": f"payload over {MAX_BODY // 1000} KB"})
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid JSON body"})
            self._run(post, data)

        def log_message(self, *a):
            pass

    return handler

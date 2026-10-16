"""WSGI entrypoint (stdlib only): serves public/ and routes /api/* to demo_api.

Vercel picks up the ``app`` callable from this file; locally run scripts/dev_server.py.
"""
import json
import mimetypes
import os

from demo_api import handle

PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
SECURITY = [("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer")]
STATUS = {200: "OK", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed",
          413: "Payload Too Large", 500: "Internal Server Error"}


def _respond(start, status, body, ctype, extra=()):
    start(f"{status} {STATUS.get(status, '')}",
          [("Content-Type", ctype), ("Content-Length", str(len(body))), *SECURITY, *extra])
    return [body]


def app(environ, start_response):
    method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "/")
    if path.startswith("/api/"):
        n = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(min(n, 300_001)) if n else b""
        status, payload = handle(method, path + ("?" + environ["QUERY_STRING"]
                                                 if environ.get("QUERY_STRING") else ""), body)
        return _respond(start_response, status,
                        json.dumps(payload, ensure_ascii=False, default=str).encode(),
                        "application/json; charset=utf-8", [("Cache-Control", "no-store")])
    if method not in ("GET", "HEAD"):
        return _respond(start_response, 405, b"method not allowed", "text/plain")
    rel = "index.html" if path in ("", "/") else path.lstrip("/")
    full = os.path.realpath(os.path.join(PUBLIC, rel))
    if not full.startswith(os.path.realpath(PUBLIC) + os.sep) or not os.path.isfile(full):
        return _respond(start_response, 404, b"not found", "text/plain")
    with open(full, "rb") as f:
        data = f.read()
    ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype.endswith(("javascript", "json")):
        ctype += "; charset=utf-8"
    return _respond(start_response, 200, data, ctype)

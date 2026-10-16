"""Route table and dispatcher for the demo API (pure functions, no HTTP types)."""
import json

from . import cluster, decay, faq, gsc, sample, validate
from .common import ApiError

MAX_BODY = 300_000  # bytes; the demo is a showcase, not a processing service

ROUTES = {
    "faq": (faq.get, faq.post), "validate": (None, validate.post),
    "cluster": (None, cluster.post), "gsc": (None, gsc.post),
    "decay": (None, decay.post), "sample": (sample.get, None),
}


def handle(method: str, path: str, body: bytes = b"") -> tuple[int, dict]:
    """Return (status, json-serialisable payload). Never raises."""
    name = path.split("?", 1)[0].removeprefix("/api/").strip("/")
    if name not in ROUTES:
        return 404, {"error": "not found"}
    get, post = ROUTES[name]
    try:
        if method == "GET" and get:
            return 200, get(path)
        if method == "POST" and post:
            if len(body) > MAX_BODY:
                return 413, {"error": f"payload over {MAX_BODY // 1000} KB"}
            try:
                data = json.loads(body or b"{}")
            except json.JSONDecodeError:
                return 400, {"error": "invalid JSON body"}
            if not isinstance(data, dict):
                return 400, {"error": "JSON body must be an object"}
            return 200, post(data)
        return 405, {"error": "method not allowed"}
    except ApiError as e:
        return 400, {"error": str(e)}
    except Exception as e:  # never leak a traceback to the client
        return 500, {"error": type(e).__name__}

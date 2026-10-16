import io
import json
import unittest
from pathlib import Path

from app import app
from demo_api import handle

DATA = Path(__file__).resolve().parents[1] / "data"


def call(method, path, body=b"", query=""):
    out = {}
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
           "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)}
    chunks = app(env, lambda status, headers: out.update(status=int(status.split()[0]),
                                                         headers=dict(headers)))
    return out["status"], out["headers"], b"".join(chunks)


class DemoApiTests(unittest.TestCase):
    def test_static_pages_and_traversal(self):
        status, headers, body = call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"seo-toolkit", body)
        self.assertEqual(call("GET", "/../app.py")[0], 404)
        self.assertEqual(call("GET", "/%2e%2e/app.py")[0], 404)
        self.assertEqual(call("POST", "/")[0], 405)

    def test_faq_get_and_post_over_wsgi(self):
        status, _, body = call("GET", "/api/faq")
        self.assertEqual(len(json.loads(body)["items"]), 27)
        payload = json.dumps({"items": [{"question": "Why?", "answer": "<script>x</script>" + "ok " * 20}]})
        status, _, body = call("POST", "/api/faq", payload.encode())
        text = json.loads(body)["jsonld"]["mainEntity"][0]["acceptedAnswer"]["text"]
        self.assertEqual(status, 200)
        self.assertNotIn("script", text)

    def test_sample_whitelist_and_query_string(self):
        self.assertEqual(call("GET", "/api/sample", query="name=gsc")[0], 200)
        self.assertEqual(call("GET", "/api/sample", query="name=../app.py")[0], 400)

    def test_error_contract(self):
        self.assertEqual(handle("POST", "/api/validate", b"nope")[0], 400)
        self.assertEqual(handle("POST", "/api/validate", b"[]")[0], 400)
        self.assertEqual(handle("POST", "/api/validate", b'{"html": ""}')[0], 400)
        self.assertEqual(handle("POST", "/api/gsc", b'{"csv": "a,b\\n1,2"}')[0], 400)
        self.assertEqual(handle("GET", "/api/validate")[0], 405)
        self.assertEqual(handle("GET", "/api/nope")[0], 404)
        self.assertEqual(handle("POST", "/api/faq", b"x" * 300_001)[0], 413)

    def test_every_tool_endpoint_on_sample_data(self):
        html = (DATA / "sample_page.html").read_text()
        cases = [("validate", {"html": html}), ("cluster", {"keywords": (DATA / "sample_keywords.txt").read_text()}),
                 ("gsc", {"csv": (DATA / "sample_gsc.csv").read_text(), "report": "striking"}),
                 ("decay", {"csv": (DATA / "sample_traffic.csv").read_text()})]
        for name, body in cases:
            status, payload = handle("POST", f"/api/{name}", json.dumps(body).encode())
            self.assertEqual(status, 200, name)
            self.assertNotIn("error", payload)


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import json
import threading
import unittest
from datetime import date, timedelta
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from seo_toolkit import clustering, content_decay, crawler, gsc_analyzer, log_analyzer
from seo_toolkit.cli import main
from seo_toolkit.schema import (FAQItem, article, breadcrumb_list, build_faq_page, graph,
                                load_faq_bank, organization, validate_faq, validate_html,
                                webpage, website)

DATA = Path(__file__).resolve().parents[1] / "data"


class FaqTests(unittest.TestCase):
    def test_bank_is_clean_and_text_roundtrips(self):
        items = load_faq_bank()
        self.assertGreaterEqual(len(items), 25)
        self.assertEqual(validate_faq(items), [])
        page = build_faq_page(items)
        self.assertEqual(page["mainEntity"][0]["name"], items[0].question)
        self.assertEqual(page["mainEntity"][0]["acceptedAnswer"]["text"], items[0].answer)

    def test_validation_catches_problems(self):
        bad = [FAQItem("no question mark", "short"),
               FAQItem("No question mark", "<script>x()</script>" + "word " * 20 + " buy now")]
        problems = " | ".join(validate_faq(bad))
        for needle in ("duplicate", "should end with '?'", "very short", "promotional", "HTML"):
            self.assertIn(needle, problems)

    def test_sanitizer_strips_disallowed_tags_keeps_links(self):
        node = build_faq_page([FAQItem("Q one?", '<p onclick="x">Hi <a href="https://a.io">link</a>'
                                       '<iframe src="x"></iframe> ' + "pad " * 12)], as_node=True)
        text = node["mainEntity"][0]["acceptedAnswer"]["text"]
        self.assertIn('<a href="https://a.io">link</a>', text)
        self.assertNotIn("iframe", text)
        self.assertNotIn("onclick", text)

    def test_cli_faq_output_is_complete_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["faq", "--category", "schema"])
        doc = json.loads(buf.getvalue())
        self.assertIn("only for well-known, authoritative government and health websites",
                      json.dumps(doc))


class GraphTests(unittest.TestCase):
    def build(self):
        url = "https://example.com/post"
        org = organization("https://example.com", "Example")
        web = website("https://example.com", "Example", org["@id"])
        bc = breadcrumb_list(url, [("Home", "https://example.com"), ("Post", url)])
        faq = build_faq_page([FAQItem("What is it?", "A reasonably long answer for the test case."),
                              FAQItem("Why use it?", "Another reasonably long answer for testing.")],
                             url, as_node=True)
        page = webpage(url, "Post", web["@id"], bc["@id"], faq["@id"])
        art = article(url, "Post", "A. Author", "2026-01-01", publisher_id=org["@id"])
        return graph(org, web, bc, faq, page, art, org)

    def test_graph_dedupes_and_links_resolve(self):
        g = self.build()
        ids = [n["@id"] for n in g["@graph"]]
        self.assertEqual(len(ids), len(set(ids)))
        html = ('<script type="application/ld+json">' + json.dumps(g) + "</script>"
                "<p>What is it?</p><p>Why use it?</p>")
        self.assertEqual(validate_html(html)["errors"], [])

    def test_validator_flags_missing_props_dangling_refs_and_hidden_faq(self):
        res = validate_html((DATA / "sample_page.html").read_text())
        self.assertEqual(len(res["errors"]), 1)
        self.assertIn("not visible", res["errors"][0])
        g = self.build()
        g["@graph"] = [n for n in g["@graph"] if "FAQPage" not in n["@type"]]
        html = '<script type="application/ld+json">' + json.dumps(g) + "</script>"
        self.assertTrue(any("dangling" in e for e in validate_html(html)["errors"]))
        bad = '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article"}</script>'
        self.assertTrue(any("headline" in e for e in validate_html(bad)["errors"]))
        self.assertTrue(validate_html('<script type="application/ld+json">{oops</script>')["errors"])


class GscTests(unittest.TestCase):
    def setUp(self):
        self.rows = [gsc_analyzer.Row("a", "/p1", 10, 1000, 8.0),
                     gsc_analyzer.Row("b", "/p2", 500, 1000, 2.0),
                     gsc_analyzer.Row("c", "/p3", 1, 900, 1.0),
                     gsc_analyzer.Row("a", "/p4", 5, 600, 12.0)]

    def test_striking_distance_sorted_by_potential(self):
        out = gsc_analyzer.striking_distance(self.rows)
        self.assertEqual([r["query"] for r in out], ["a", "a"])
        self.assertEqual(out[0]["page"], "/p1")

    def test_ctr_underperformers(self):
        out = gsc_analyzer.ctr_underperformers(self.rows)
        self.assertEqual(out[0]["query"], "c")

    def test_cannibalization(self):
        out = gsc_analyzer.cannibalization(self.rows)
        self.assertEqual(out[0]["query"], "a")
        self.assertEqual(len(out[0]["pages"]), 2)

    def test_sample_csv_loads(self):
        self.assertTrue(gsc_analyzer.load_csv(DATA / "sample_gsc.csv"))


class ClusterTests(unittest.TestCase):
    def test_groups_variants_and_separates_intent(self):
        kws = (DATA / "sample_keywords.txt").read_text().split("\n")
        cl = clustering.cluster([k for k in kws if k])
        by_kw = {k: c for c in cl for k in c["keywords"]}
        self.assertIs(by_kw["how to choose running shoes"], by_kw["how to choose a running shoe"])
        self.assertIsNot(by_kw["buy running shoes online"], by_kw["cheap running shoes"] and
                         by_kw["how to choose running shoes"])
        self.assertEqual(by_kw["buy running shoes online"]["intent"], "transactional")
        self.assertEqual(clustering.classify_intent("best crm tools"), "commercial")


class LogTests(unittest.TestCase):
    def test_sample_log(self):
        with open(DATA / "sample_access.log") as fh:
            r = log_analyzer.analyze(fh)
        self.assertEqual(r["total_hits"], 200)
        self.assertGreater(r["parameter_hits"], 0)
        self.assertIn("color", dict(r["top_parameters"]))
        self.assertGreater(r["wasted_pct"], 0)

    def test_parse_rejects_garbage_and_detects_ai_bots(self):
        self.assertIsNone(log_analyzer.parse_line("garbage"))
        h = log_analyzer.parse_line('1.1.1.1 - - [d] "GET / HTTP/1.1" 200 1 "-" "Mozilla GPTBot/1.0"')
        self.assertEqual(h.bot, "GPTBot")


class DecayTests(unittest.TestCase):
    def test_flags_only_declining_page(self):
        end = date(2026, 3, 1)
        first = end - timedelta(days=55)
        shapes = {"/down": lambda k: 100 - k, "/flat": lambda k: 50, "/up": lambda k: 10 + k}
        data = {p: {first + timedelta(days=k): f(k) for k in range(56)} for p, f in shapes.items()}
        out = content_decay.detect(data, today=end)
        self.assertEqual([o["page"] for o in out], ["/down"])

    def test_slope(self):
        self.assertAlmostEqual(content_decay.slope([1, 2, 3, 4]), 1.0)


class _Site(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        routes = {
            "/": (200, '<title>Home</title><meta name="description" content="d"><h1>H</h1>'
                       '<link rel="canonical" href="/"><a href="/a">a</a><a href="/old">o</a>'),
            "/a": (200, "<title>Home</title><h1>A</h1><h1>B</h1>"),
            "/old": (301, "/hop"), "/hop": (301, "/a"),
        }
        status, body = routes.get(self.path, (404, ""))
        self.send_response(status)
        if status == 301:
            self.send_header("Location", body)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if status == 200:
            self.wfile.write(body.encode())


class CrawlerTests(unittest.TestCase):
    def test_crawl_and_audit(self):
        srv = HTTPServer(("127.0.0.1", 0), _Site)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            pages = crawler.crawl(f"http://127.0.0.1:{srv.server_port}/", max_pages=10)
        finally:
            srv.shutdown()
            srv.server_close()
        text = " | ".join(i["issue"] for i in crawler.audit(pages))
        for needle in ("duplicate title", "redirect chain of 2 hops", "missing meta description",
                       "2 <h1> elements"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()

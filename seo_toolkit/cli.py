"""Command line entry point: python -m seo_toolkit <command> ..."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import clustering, content_decay, crawler, gsc_analyzer, log_analyzer
from .schema import (build_faq_page, extract_jsonld, load_faq_bank, load_faq_file,
                     validate_faq, validate_html)
from .schema.faq import render_visible_html


def _dump(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="seo_toolkit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gsc", help="analyse a Search Console CSV export")
    g.add_argument("csv")
    g.add_argument("--report", choices=["striking", "ctr", "cannibal"], default="striking")

    c = sub.add_parser("crawl", help="crawl a site and list technical issues")
    c.add_argument("url")
    c.add_argument("--max-pages", type=int, default=100)

    k = sub.add_parser("cluster", help="cluster keywords from a text file (one per line)")
    k.add_argument("file")
    k.add_argument("--threshold", type=float, default=0.5)

    lg = sub.add_parser("logs", help="analyse bot crawl behaviour in an access log")
    lg.add_argument("file")
    lg.add_argument("--bot", default="Googlebot")

    d = sub.add_parser("decay", help="find pages losing organic clicks")
    d.add_argument("csv")
    d.add_argument("--window", type=int, default=28)

    f = sub.add_parser("faq", help="build FAQPage JSON-LD")
    f.add_argument("--file", help="JSON or Markdown Q&A file; omit to use the built-in bank")
    f.add_argument("--category", help="limit the built-in bank to one category")
    f.add_argument("--url", help="page URL, used for the node @id")
    f.add_argument("--html", action="store_true", help="also print matching visible HTML")

    s = sub.add_parser("schema-check", help="validate JSON-LD in an HTML file")
    s.add_argument("html")

    a = ap.parse_args(argv)

    if a.cmd == "gsc":
        rows = gsc_analyzer.load_csv(a.csv)
        fn = {"striking": gsc_analyzer.striking_distance,
              "ctr": gsc_analyzer.ctr_underperformers,
              "cannibal": gsc_analyzer.cannibalization}[a.report]
        _dump(fn(rows))
    elif a.cmd == "crawl":
        _dump(crawler.audit(crawler.crawl(a.url, max_pages=a.max_pages)))
    elif a.cmd == "cluster":
        kws = [l.strip() for l in Path(a.file).read_text().splitlines() if l.strip()]
        _dump(clustering.cluster(kws, threshold=a.threshold))
    elif a.cmd == "logs":
        with open(a.file, encoding="utf-8", errors="replace") as fh:
            _dump(log_analyzer.analyze(fh, bot=a.bot))
    elif a.cmd == "decay":
        _dump(content_decay.detect(content_decay.load(a.csv), window_days=a.window))
    elif a.cmd == "faq":
        items = load_faq_file(a.file) if a.file else load_faq_bank(a.category)
        for p in validate_faq(items):
            print(f"warning: {p}", file=sys.stderr)
        _dump(build_faq_page(items, a.url))
        if a.html:
            print(render_visible_html(items))
    elif a.cmd == "schema-check":
        result = validate_html(Path(a.html).read_text(encoding="utf-8"))
        _dump(result)
        return 1 if result["errors"] else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

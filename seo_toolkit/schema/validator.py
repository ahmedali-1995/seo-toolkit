"""Extract and validate JSON-LD from HTML.

Checks: JSON parses, ``@graph`` ids resolve, required properties per type, and
FAQ/visible-content parity (marked-up Q&A must appear in the page body).
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any

REQUIRED: dict[str, list[str]] = {
    "Organization": ["name", "url"],
    "WebSite": ["url", "name"],
    "WebPage": ["url"],
    "Article": ["headline", "author", "datePublished"],
    "NewsArticle": ["headline", "author", "datePublished"],
    "BlogPosting": ["headline", "author", "datePublished"],
    "Product": ["name", "offers"],
    "Offer": ["price", "priceCurrency"],
    "BreadcrumbList": ["itemListElement"],
    "ListItem": ["position", "name"],
    "FAQPage": ["mainEntity"],
    "Question": ["name", "acceptedAnswer"],
    "Answer": ["text"],
}


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.body: list[str] = []
        self._in_ld = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            if dict(attrs).get("type") == "application/ld+json":
                self._in_ld = True
                self.blocks.append("")
            else:
                self._skip += 1
        elif tag == "style":
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self._in_ld = False
        elif tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_ld:
            self.blocks[-1] += data
        elif not self._skip:
            self.body.append(data)


def extract_jsonld(html: str) -> tuple[list[Any], list[str], str]:
    """Return (parsed_docs, parse_errors, visible_text)."""
    c = _Collector()
    c.feed(html)
    docs, errors = [], []
    for i, raw in enumerate(c.blocks, start=1):
        try:
            docs.append(json.loads(raw))
        except json.JSONDecodeError as e:
            errors.append(f"block {i}: invalid JSON ({e.msg} at line {e.lineno})")
    return docs, errors, re.sub(r"\s+", " ", " ".join(c.body)).strip()


def _types(node: dict) -> list[str]:
    t = node.get("@type", [])
    return [t] if isinstance(t, str) else list(t)


def validate_node(node: dict, path: str = "$") -> list[str]:
    out: list[str] = []
    for t in _types(node):
        for prop in REQUIRED.get(t, []):
            if node.get(prop) in (None, "", [], {}):
                out.append(f"{path} ({t}): missing required property '{prop}'")
    for k, v in node.items():
        kids = v if isinstance(v, list) else [v]
        for j, kid in enumerate(kids):
            if isinstance(kid, dict) and "@type" in kid:
                out.extend(validate_node(kid, f"{path}.{k}[{j}]"))
    return out


def _flatten(doc: Any) -> list[dict]:
    if isinstance(doc, list):
        return [n for d in doc for n in _flatten(d)]
    if isinstance(doc, dict):
        return _flatten(doc["@graph"]) if "@graph" in doc else [doc]
    return []


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", re.sub(r"<[^>]+>", " ", s).lower()).strip()


def validate_html(html: str) -> dict[str, list[str]]:
    """Return {'errors': [...], 'warnings': [...]}."""
    docs, errors, visible = extract_jsonld(html)
    warnings: list[str] = []
    if not docs and not errors:
        warnings.append("no JSON-LD found")
    nodes = _flatten(docs)
    ids = {n["@id"] for n in nodes if "@id" in n}
    for n in nodes:
        errors.extend(validate_node(n, n.get("@id", f"${'/'.join(_types(n))}")))
        if "@context" not in n and not any("@graph" in d for d in docs if isinstance(d, dict)):
            warnings.append(f"{'/'.join(_types(n))}: no @context")
    # @id references that point to this page's own fragments must exist.
    blob = json.dumps(docs)
    for ref in set(re.findall(r'\{"@id": "([^"]+)"\}', blob)):
        if "#" in ref and ref not in ids:
            errors.append(f"dangling reference: {ref} not defined in any block")
    # FAQ parity with visible text.
    vis = _norm(visible)
    for n in nodes:
        if "FAQPage" in _types(n):
            for q in n.get("mainEntity", []):
                if _norm(q.get("name", "")) not in vis:
                    errors.append(f"FAQ question not visible on page: {q.get('name')!r}")
    return {"errors": errors, "warnings": warnings}

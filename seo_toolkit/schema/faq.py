"""FAQPage generation and validation.

Input formats: JSON (list of {question, answer, category?}) or Markdown
(``## Question`` headings followed by the answer). Answers may contain the small
HTML subset Google documents for FAQ answers; anything else is stripped.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ALLOWED_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "br", "ol", "ul", "li", "a",
                "p", "div", "b", "strong", "i", "em"}
BANK_PATH = Path(__file__).resolve().parents[2] / "data" / "faq_bank.json"


@dataclass
class FAQItem:
    question: str
    answer: str
    category: str = "general"
    issues: list[str] = field(default_factory=list, repr=False)


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            return
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith(("http://", "https://", "/")):
                self.out.append(f'<a href="{href}">')
            else:
                self.out.append("<a>")
        else:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in ALLOWED_TAGS and tag != "br":
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(data)


def sanitize_answer(html: str) -> str:
    s = _Sanitizer()
    s.feed(html)
    return re.sub(r"\s+", " ", "".join(s.out)).strip()


def plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def load_faq_file(path: str | Path) -> list[FAQItem]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return [FAQItem(d["question"], d["answer"], d.get("category", "general"))
                for d in json.loads(text)]
    items: list[FAQItem] = []
    for block in re.split(r"(?m)^##\s+", text)[1:]:
        q, _, a = block.partition("\n")
        items.append(FAQItem(q.strip(), a.strip()))
    return items


def load_faq_bank(category: str | None = None) -> list[FAQItem]:
    items = load_faq_file(BANK_PATH)
    return [i for i in items if category in (None, i.category)]


def validate_faq(items: list[FAQItem], min_items: int = 2) -> list[str]:
    """Return a list of human-readable problems (empty list == clean)."""
    problems: list[str] = []
    seen: dict[str, int] = {}
    if len(items) < min_items:
        problems.append(f"only {len(items)} item(s); FAQPage needs at least {min_items}")
    for n, it in enumerate(items, start=1):
        key = re.sub(r"\W+", " ", it.question.lower()).strip()
        if key in seen:
            problems.append(f"#{n}: duplicate of question #{seen[key]}: {it.question!r}")
        seen[key] = n
        if not it.question.strip().endswith("?"):
            problems.append(f"#{n}: question should end with '?': {it.question!r}")
        if len(plain_text(it.answer)) < 40:
            problems.append(f"#{n}: answer is very short (<40 chars): {it.question!r}")
        if len(plain_text(it.answer)) > 1500:
            problems.append(f"#{n}: answer over 1500 chars; trim or link out: {it.question!r}")
        if re.search(r"(?i)\b(buy now|click here|best price|discount code)\b", it.answer):
            problems.append(f"#{n}: promotional wording; FAQ answers must be informational")
        if sanitize_answer(it.answer) != re.sub(r"\s+", " ", it.answer).strip():
            problems.append(f"#{n}: contains HTML outside the allowed subset (will be stripped)")
    return problems


def build_faq_page(items: list[FAQItem], page_url: str | None = None,
                   as_node: bool = False) -> dict:
    """Build FAQPage JSON-LD. ``as_node=True`` omits @context for use inside @graph."""
    node = {
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": it.question.strip(),
             "acceptedAnswer": {"@type": "Answer", "text": sanitize_answer(it.answer)}}
            for it in items
        ],
    }
    if page_url:
        node["@id"] = f"{page_url}#faq"
    if as_node:
        return node
    return {"@context": "https://schema.org", **node}


def render_visible_html(items: list[FAQItem]) -> str:
    """Matching on-page markup. Google requires FAQ content to be visible to users."""
    parts = ['<section class="faq">']
    for it in items:
        parts.append(f"  <details><summary>{it.question}</summary>"
                     f"<div>{sanitize_answer(it.answer)}</div></details>")
    parts.append("</section>")
    return "\n".join(parts)

"""Small polite site crawler for technical SEO audits (stdlib only)."""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

UA = "seo-toolkit-crawler/0.1 (+audit)"
MAX_HOPS = 10


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


@dataclass
class Page:
    url: str
    status: int = 0
    final_url: str = ""
    redirect_chain: list[str] = field(default_factory=list)
    title: str = ""
    description: str = ""
    canonical: str = ""
    robots: str = ""
    h1: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    load_ms: int = 0
    error: str = ""


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = self.description = self.canonical = self.robots = ""
        self.h1: list[str] = []
        self.links: list[str] = []
        self._tag = ""
        self._buf = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("title", "h1"):
            self._tag, self._buf = tag, ""
        elif tag == "meta":
            name = (a.get("name") or "").lower()
            if name == "description":
                self.description = (a.get("content") or "").strip()
            elif name == "robots":
                self.robots = (a.get("content") or "").lower()
        elif tag == "link" and "canonical" in (a.get("rel") or "").lower():
            self.canonical = a.get("href") or ""
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_data(self, data):
        if self._tag:
            self._buf += data

    def handle_endtag(self, tag):
        if tag == self._tag:
            text = re.sub(r"\s+", " ", self._buf).strip()
            if tag == "title" and not self.title:
                self.title = text
            elif tag == "h1":
                self.h1.append(text)
            self._tag = ""


def fetch(url: str, timeout: float = 10) -> Page:
    """Fetch one URL, following redirects manually so the chain is recorded."""
    page = Page(url=url)
    current = url
    start = time.monotonic()
    for _ in range(MAX_HOPS):
        req = urllib.request.Request(current, headers={"User-Agent": UA})
        try:
            resp = _opener.open(req, timeout=timeout)
            with resp:
                status, headers, body = resp.status, resp.headers, resp.read(2_000_000)
        except urllib.error.HTTPError as e:
            e.close()
            status, headers, body = e.code, e.headers, b""
        except Exception as e:  # network errors, timeouts, bad TLS
            page.error = f"{type(e).__name__}: {e}"
            return page
        if status in (301, 302, 303, 307, 308) and headers.get("Location"):
            current = urljoin(current, headers["Location"])
            page.redirect_chain.append(current)
            continue
        page.status, page.final_url = status, current
        page.load_ms = int((time.monotonic() - start) * 1000)
        if "html" in (headers.get("Content-Type") or "") and body:
            p = _Parser()
            p.feed(body.decode("utf-8", "replace"))
            page.title, page.description = p.title, p.description
            page.canonical, page.robots, page.h1 = p.canonical, p.robots, p.h1
            page.links = [urldefrag(urljoin(current, h))[0] for h in p.links
                          if not h.startswith(("mailto:", "tel:", "javascript:"))]
        return page
    page.error = f"redirect loop (> {MAX_HOPS} hops)"
    return page


def crawl(start_url: str, max_pages: int = 200, workers: int = 4,
          delay: float = 0.0, respect_robots: bool = True) -> list[Page]:
    host = urlparse(start_url).netloc
    rp = RobotFileParser(urljoin(start_url, "/robots.txt"))
    if respect_robots:
        try:
            rp.read()
        except Exception:
            respect_robots = False
    seen, queue, pages = {start_url}, deque([start_url]), []
    with ThreadPoolExecutor(workers) as pool:
        while queue and len(pages) < max_pages:
            batch = []
            while queue and len(batch) < workers and len(pages) + len(batch) < max_pages:
                u = queue.popleft()
                if respect_robots and not rp.can_fetch(UA, u):
                    continue
                batch.append(u)
            for pg in pool.map(fetch, batch):
                pages.append(pg)
                for link in pg.links:
                    if urlparse(link).netloc == host and link not in seen \
                            and urlparse(link).scheme in ("http", "https"):
                        seen.add(link)
                        queue.append(link)
            if delay:
                time.sleep(delay)
    return pages


def audit(pages: list[Page]) -> list[dict]:
    """Turn crawl results into a flat list of issues: {severity, url, issue}."""
    issues: list[dict] = []

    def add(sev, url, msg):
        issues.append({"severity": sev, "url": url, "issue": msg})

    titles = Counter(p.title for p in pages if p.title)
    descs = Counter(p.description for p in pages if p.description)
    for p in pages:
        if p.error:
            add("error", p.url, f"fetch failed: {p.error}")
            continue
        if len(p.redirect_chain) > 1:
            add("warning", p.url, f"redirect chain of {len(p.redirect_chain)} hops")
        if p.status >= 500:
            add("error", p.url, f"server error {p.status}")
        elif p.status >= 400:
            add("error", p.url, f"client error {p.status}")
        if p.status != 200:
            continue
        if not p.title:
            add("error", p.url, "missing <title>")
        elif titles[p.title] > 1:
            add("warning", p.url, "duplicate title")
        elif len(p.title) > 60:
            add("info", p.url, f"title long ({len(p.title)} chars)")
        if not p.description:
            add("warning", p.url, "missing meta description")
        elif descs[p.description] > 1:
            add("warning", p.url, "duplicate meta description")
        if len(p.h1) == 0:
            add("warning", p.url, "no <h1>")
        elif len(p.h1) > 1:
            add("info", p.url, f"{len(p.h1)} <h1> elements")
        if not p.canonical:
            add("info", p.url, "no canonical tag")
        elif urldefrag(p.canonical)[0].rstrip("/") != p.url.rstrip("/"):
            add("info", p.url, f"canonical points elsewhere: {p.canonical}")
        if "noindex" in p.robots:
            add("info", p.url, "noindex")
        if p.load_ms > 1500:
            add("warning", p.url, f"slow response ({p.load_ms} ms)")
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(issues, key=lambda i: (order[i["severity"]], i["url"]))

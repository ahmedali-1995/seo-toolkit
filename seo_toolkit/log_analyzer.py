"""Server log analysis for crawl behaviour (combined log format)."""
from __future__ import annotations

import re
import socket
from collections import Counter
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

LINE = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) [^"]*" '
    r'(?P<status>\d{3}) (?P<size>\S+) "(?P<ref>[^"]*)" "(?P<ua>[^"]*)"')

BOTS = {"googlebot": "Googlebot", "bingbot": "Bingbot", "gptbot": "GPTBot",
        "claudebot": "ClaudeBot", "perplexitybot": "PerplexityBot",
        "applebot": "Applebot", "yandexbot": "YandexBot"}
STATIC = re.compile(r"\.(css|js|png|jpe?g|gif|svg|webp|ico|woff2?|map)$", re.I)


@dataclass
class Hit:
    ip: str
    path: str
    status: int
    ua: str
    bot: str | None


def parse_line(line: str) -> Hit | None:
    m = LINE.match(line)
    if not m:
        return None
    ua = m["ua"].lower()
    bot = next((name for key, name in BOTS.items() if key in ua), None)
    return Hit(m["ip"], m["path"], int(m["status"]), m["ua"], bot)


def verify_googlebot(ip: str) -> bool:  # pragma: no cover - needs network
    """Reverse-DNS + forward-confirm, the method Google documents."""
    try:
        host = socket.gethostbyaddr(ip)[0]
        if not host.endswith((".googlebot.com", ".google.com")):
            return False
        return ip in socket.gethostbyname_ex(host)[2]
    except OSError:
        return False


def analyze(lines, bot: str = "Googlebot", top: int = 10) -> dict:
    hits = [h for h in map(parse_line, lines) if h and h.bot == bot]
    total = len(hits)
    status = Counter(h.status for h in hits)
    paths = Counter(urlparse(h.path).path for h in hits)
    sections = Counter("/" + urlparse(h.path).path.strip("/").split("/")[0] for h in hits)
    params = [h for h in hits if urlparse(h.path).query]
    param_keys = Counter(k for h in params for k in parse_qs(urlparse(h.path).query))
    static = sum(1 for h in hits if STATIC.search(urlparse(h.path).path))
    wasted = [h for h in hits if h.status in (301, 302, 404, 410) or h.status >= 500
              or urlparse(h.path).query]
    pct = lambda n: round(100 * n / total, 1) if total else 0.0
    return {
        "bot": bot, "total_hits": total,
        "status": dict(sorted(status.items())),
        "top_paths": paths.most_common(top),
        "top_sections": sections.most_common(top),
        "parameter_hits": len(params), "parameter_pct": pct(len(params)),
        "top_parameters": param_keys.most_common(top),
        "static_asset_pct": pct(static),
        "wasted_pct": pct(len(wasted)),
        "unique_urls": len(paths),
    }

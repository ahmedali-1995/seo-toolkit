"""Search Console performance analysis.

Works on a Search Console export (CSV with query, page, clicks, impressions,
ctr, position) so it runs offline; ``fetch_from_api`` pulls the same shape
from the Search Analytics API when google-api-python-client is installed.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# Rough organic CTR by position (industry-average curve; override per site).
EXPECTED_CTR = {1: .28, 2: .15, 3: .10, 4: .07, 5: .05, 6: .04, 7: .03, 8: .025,
                9: .02, 10: .018}


@dataclass
class Row:
    query: str
    page: str
    clicks: int
    impressions: int
    position: float

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0


def load_csv(path: str | Path) -> list[Row]:
    with open(path, newline="", encoding="utf-8") as f:
        return [Row(r["query"], r["page"], int(r["clicks"]), int(r["impressions"]),
                    float(r["position"])) for r in csv.DictReader(f)]


def fetch_from_api(site_url: str, start: str, end: str, credentials_file: str,
                   row_limit: int = 25000) -> list[Row]:  # pragma: no cover
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    rows, start_row = [], 0
    while True:
        resp = svc.searchanalytics().query(siteUrl=site_url, body={
            "startDate": start, "endDate": end, "dimensions": ["query", "page"],
            "rowLimit": min(row_limit, 25000), "startRow": start_row}).execute()
        batch = resp.get("rows", [])
        rows += [Row(r["keys"][0], r["keys"][1], int(r["clicks"]),
                     int(r["impressions"]), r["position"]) for r in batch]
        if len(batch) < 25000 or len(rows) >= row_limit:
            return rows
        start_row += 25000


def striking_distance(rows: list[Row], lo: float = 4, hi: float = 15,
                      min_impressions: int = 100) -> list[dict]:
    """Queries on page 1 bottom / page 2 with enough demand to be worth pushing.

    ``potential_clicks`` estimates the gain from reaching position 3 using the
    expected-CTR curve.
    """
    out = []
    for r in rows:
        if lo <= r.position <= hi and r.impressions >= min_impressions:
            gain = r.impressions * EXPECTED_CTR[3] - r.clicks
            out.append({"query": r.query, "page": r.page, "position": round(r.position, 1),
                        "impressions": r.impressions, "clicks": r.clicks,
                        "potential_clicks": max(0, round(gain))})
    return sorted(out, key=lambda x: -x["potential_clicks"])


def ctr_underperformers(rows: list[Row], ratio: float = 0.6,
                        min_impressions: int = 200) -> list[dict]:
    """Rows whose CTR is below ``ratio`` x the expected CTR for their position."""
    out = []
    for r in rows:
        pos = round(r.position)
        exp = EXPECTED_CTR.get(pos)
        if exp is None or r.impressions < min_impressions:
            continue
        if r.ctr < exp * ratio:
            out.append({"query": r.query, "page": r.page, "position": round(r.position, 1),
                        "ctr": round(r.ctr, 4), "expected_ctr": exp,
                        "missed_clicks": round(r.impressions * exp - r.clicks)})
    return sorted(out, key=lambda x: -x["missed_clicks"])


def cannibalization(rows: list[Row], min_impressions: int = 50) -> list[dict]:
    """Queries where more than one URL earns meaningful impressions."""
    by_q: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        if r.impressions >= min_impressions:
            by_q[r.query].append(r)
    out = []
    for q, rs in by_q.items():
        if len({r.page for r in rs}) > 1:
            rs.sort(key=lambda r: -r.impressions)
            out.append({"query": q, "pages": [(r.page, round(r.position, 1), r.impressions)
                                              for r in rs],
                        "total_impressions": sum(r.impressions for r in rs)})
    return sorted(out, key=lambda x: -x["total_impressions"])

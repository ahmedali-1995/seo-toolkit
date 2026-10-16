"""Detect pages whose organic traffic is declining.

Input CSV: date (YYYY-MM-DD), page, clicks (daily or weekly rows).
Compares the most recent window to the previous equal window and also fits a
linear trend, so one-off spikes in the baseline don't mask a steady decline.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


def load(path: str | Path) -> dict[str, dict[date, int]]:
    data: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            data[r["page"]][date.fromisoformat(r["date"])] += int(r["clicks"])
    return data


def slope(ys: list[float]) -> float:
    """Least-squares slope of ys against 0..n-1."""
    n = len(ys)
    if n < 2:
        return 0.0
    mx, my = (n - 1) / 2, sum(ys) / n
    den = sum((i - mx) ** 2 for i in range(n))
    return sum((i - mx) * (y - my) for i, y in enumerate(ys)) / den


def detect(data: dict[str, dict[date, int]], window_days: int = 28,
           min_clicks: int = 50, min_drop_pct: float = 20.0,
           today: date | None = None) -> list[dict]:
    today = today or max(d for series in data.values() for d in series)
    cur_start = today - timedelta(days=window_days - 1)
    prev_start = cur_start - timedelta(days=window_days)
    out = []
    for page, series in data.items():
        cur = sum(c for d, c in series.items() if cur_start <= d <= today)
        prev = sum(c for d, c in series.items() if prev_start <= d < cur_start)
        if prev < min_clicks:
            continue
        drop = 100 * (prev - cur) / prev
        trend = slope([series.get(prev_start + timedelta(days=i), 0)
                       for i in range(window_days * 2)])
        if drop >= min_drop_pct and trend < 0:
            out.append({"page": page, "previous": prev, "current": cur,
                        "drop_pct": round(drop, 1), "lost_clicks": prev - cur,
                        "trend_per_day": round(trend, 3)})
    return sorted(out, key=lambda x: -x["lost_clicks"])

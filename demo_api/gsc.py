import os
import tempfile

from .common import ApiError
from seo_toolkit import gsc_analyzer as g

REPORTS = {"striking": g.striking_distance, "ctr": g.ctr_underperformers,
           "cannibal": g.cannibalization}


def post(d):
    report = d.get("report", "striking")
    if report not in REPORTS:
        raise ApiError("unknown report")
    text = str(d.get("csv", ""))
    if text.count("\n") > 5000:
        raise ApiError("max 5000 rows")
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(text)
    try:
        rows = g.load_csv(f.name)
    except (KeyError, ValueError):
        raise ApiError("CSV needs columns: query,page,clicks,impressions,ctr,position")
    finally:
        os.unlink(f.name)
    return {"rows": len(rows), "results": REPORTS[report](rows)[:100]}


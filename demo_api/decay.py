import os
import tempfile

from .common import ApiError
from seo_toolkit import content_decay as c


def post(d):
    text = str(d.get("csv", ""))
    if text.count("\n") > 20000:
        raise ApiError("max 20000 rows")
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(text)
    try:
        data = c.load(f.name)
        if not data:
            raise ApiError("no rows found")
        window = min(max(int(d.get("window", 28)), 7), 90)
        return {"pages": len(data), "results": c.detect(data, window_days=window)}
    except (KeyError, ValueError):
        raise ApiError("CSV needs columns: date (YYYY-MM-DD),page,clicks")
    finally:
        os.unlink(f.name)


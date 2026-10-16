from .common import ApiError
from seo_toolkit.clustering import cluster


def post(d):
    kws = [k.strip() for k in str(d.get("keywords", "")).splitlines() if k.strip()]
    if not kws:
        raise ApiError("enter at least one keyword")
    if len(kws) > 2000:
        raise ApiError("max 2000 keywords")
    th = min(max(float(d.get("threshold", 0.5)), 0.1), 0.95)
    return {"clusters": cluster(kws, threshold=th), "total": len(set(kws))}


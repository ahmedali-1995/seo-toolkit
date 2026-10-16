import os
from urllib.parse import parse_qs, urlparse

from .common import ApiError

FILES = {"gsc": "sample_gsc.csv", "decay": "sample_traffic.csv",
         "keywords": "sample_keywords.txt", "page": "sample_page.html"}
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def get(path):
    name = parse_qs(urlparse(path).query).get("name", [""])[0]
    if name not in FILES:
        raise ApiError("unknown sample")
    with open(os.path.join(DATA, FILES[name]), encoding="utf-8") as f:
        return {"text": f.read()}


from .common import ApiError
from seo_toolkit.schema import extract_jsonld, validate_html


def post(d):
    html = str(d.get("html", ""))
    if not html.strip():
        raise ApiError("paste some HTML first")
    docs, _, _ = extract_jsonld(html)
    return {**validate_html(html), "blocks": len(docs)}


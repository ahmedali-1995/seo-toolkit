from _common import ApiError, make_handler
from seo_toolkit.schema import FAQItem, build_faq_page, load_faq_bank, validate_faq
from seo_toolkit.schema.faq import render_visible_html


def post(d):
    raw = d.get("items") or []
    if len(raw) > 100:
        raise ApiError("max 100 items")
    items = [FAQItem(str(i.get("question", "")), str(i.get("answer", ""))) for i in raw] \
        if raw else load_faq_bank(d.get("category") or None)
    url = d.get("url") or None
    return {"count": len(items), "warnings": validate_faq(items),
            "jsonld": build_faq_page(items, url), "html": render_visible_html(items)}


def get(_path):
    bank = load_faq_bank()
    return {"items": [{"question": i.question, "answer": i.answer, "category": i.category}
                      for i in bank], "categories": sorted({i.category for i in bank})}


handler = make_handler(post, get)

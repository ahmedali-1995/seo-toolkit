"""JSON-LD node builders.

Every node gets a stable ``@id`` (``<url>#<fragment>``) so nodes can reference
each other inside one ``@graph`` instead of being duplicated per block. That is
the main difference between "pasted schema snippets" and a real entity graph.
"""
from __future__ import annotations

from typing import Any

CONTEXT = "https://schema.org"


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    """Drop None / empty values so output never contains empty properties."""
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _ref(node_id: str | None) -> dict[str, str] | None:
    return {"@id": node_id} if node_id else None


def organization(url: str, name: str, logo: str | None = None,
                 same_as: list[str] | None = None) -> dict:
    return _clean({
        "@type": "Organization", "@id": f"{url.rstrip('/')}/#organization",
        "name": name, "url": url,
        "logo": {"@type": "ImageObject", "url": logo} if logo else None,
        "sameAs": same_as,
    })


def website(url: str, name: str, publisher_id: str | None = None,
            search_url_template: str | None = None) -> dict:
    node = {
        "@type": "WebSite", "@id": f"{url.rstrip('/')}/#website",
        "url": url, "name": name, "publisher": _ref(publisher_id),
    }
    if search_url_template:
        node["potentialAction"] = {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": search_url_template},
            "query-input": "required name=search_term_string",
        }
    return _clean(node)


def webpage(url: str, name: str, website_id: str | None = None,
            breadcrumb_id: str | None = None, main_entity_id: str | None = None,
            description: str | None = None, page_type: str = "WebPage") -> dict:
    return _clean({
        "@type": page_type, "@id": f"{url}#webpage", "url": url, "name": name,
        "description": description, "isPartOf": _ref(website_id),
        "breadcrumb": _ref(breadcrumb_id), "mainEntity": _ref(main_entity_id),
    })


def breadcrumb_list(page_url: str, trail: list[tuple[str, str]]) -> dict:
    """``trail`` is [(name, url), ...] from root to current page."""
    return {
        "@type": "BreadcrumbList", "@id": f"{page_url}#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": n, "item": u}
            for i, (n, u) in enumerate(trail, start=1)
        ],
    }


def article(url: str, headline: str, author_name: str, published: str,
            modified: str | None = None, image: str | None = None,
            publisher_id: str | None = None, article_type: str = "Article") -> dict:
    return _clean({
        "@type": article_type, "@id": f"{url}#article", "headline": headline[:110],
        "author": {"@type": "Person", "name": author_name},
        "datePublished": published, "dateModified": modified or published,
        "image": image, "publisher": _ref(publisher_id),
        "mainEntityOfPage": {"@id": f"{url}#webpage"},
    })


def product(url: str, name: str, price: float, currency: str, sku: str | None = None,
            brand: str | None = None, image: str | None = None,
            availability: str = "InStock", rating: float | None = None,
            review_count: int | None = None) -> dict:
    node = {
        "@type": "Product", "@id": f"{url}#product", "name": name, "sku": sku,
        "image": image, "brand": {"@type": "Brand", "name": brand} if brand else None,
        "offers": {
            "@type": "Offer", "url": url, "price": f"{price:.2f}",
            "priceCurrency": currency,
            "availability": f"https://schema.org/{availability}",
        },
    }
    if rating is not None and review_count:
        node["aggregateRating"] = {"@type": "AggregateRating",
                                   "ratingValue": rating, "reviewCount": review_count}
    return _clean(node)


def graph(*nodes: dict) -> dict:
    """Combine nodes into a single @graph document, dropping duplicate @ids."""
    seen: set[str] = set()
    out = []
    for n in nodes:
        nid = n.get("@id")
        if nid and nid in seen:
            continue
        if nid:
            seen.add(nid)
        out.append(n)
    return {"@context": CONTEXT, "@graph": out}

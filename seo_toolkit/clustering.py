"""Keyword clustering by lexical similarity + intent labelling (stdlib only).

Single-pass greedy clustering over TF-IDF vectors with cosine similarity.
O(n * k) for k clusters. For semantic grouping on large lists, swap
``vectorise`` for an embedding model; the rest of the pipeline is unchanged.
"""
from __future__ import annotations

import math
import re
from collections import Counter

STOP = {"a", "an", "the", "of", "for", "to", "in", "on", "and", "or", "is", "are",
        "with", "my", "your", "how", "do", "does", "i", "me", "vs"}

INTENT_RULES = [
    ("transactional", r"\b(buy|price|prices|cheap|discount|coupon|order|shop|deal|for sale|near me)\b"),
    ("commercial", r"\b(best|top|review|reviews|compare|comparison|alternative|alternatives|vs)\b"),
    ("navigational", r"\b(login|log in|sign in|official|website|app download)\b"),
    ("informational", r"\b(what|why|how|when|guide|tutorial|learn|examples?|meaning|ideas?)\b"),
]


def stem(w: str) -> str:
    for suf in ("ing", "ies", "es", "s", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def tokens(kw: str) -> list[str]:
    return [stem(t) for t in re.findall(r"[a-z0-9]+", kw.lower()) if t not in STOP]


def classify_intent(kw: str) -> str:
    for label, pat in INTENT_RULES:
        if re.search(pat, kw.lower()):
            return label
    return "informational"


def vectorise(keywords: list[str]) -> list[dict[str, float]]:
    docs = [tokens(k) for k in keywords]
    df = Counter(t for d in docs for t in set(d))
    n = len(docs)
    vecs = []
    for d in docs:
        tf = Counter(d)
        v = {t: (1 + math.log(c)) * (math.log((1 + n) / (1 + df[t])) + 1) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def cluster(keywords: list[str], volumes: dict[str, int] | None = None,
            threshold: float = 0.5) -> list[dict]:
    """Group keywords. Highest-volume keyword in each cluster becomes its head term.

    Keywords of different intent are never merged: they need different pages.
    """
    volumes = volumes or {}
    order = sorted(set(keywords), key=lambda k: (-volumes.get(k, 0), k))
    vecs = dict(zip(order, vectorise(order)))
    clusters: list[dict] = []
    for kw in order:
        intent = classify_intent(kw)
        best, best_sim = None, 0.0
        for c in clusters:
            if c["intent"] != intent:
                continue
            sim = cosine(vecs[kw], vecs[c["head"]])
            if sim > best_sim:
                best, best_sim = c, sim
        if best and best_sim >= threshold:
            best["keywords"].append(kw)
        else:
            clusters.append({"head": kw, "intent": intent, "keywords": [kw]})
    for c in clusters:
        c["volume"] = sum(volumes.get(k, 0) for k in c["keywords"])
    return sorted(clusters, key=lambda c: (-c["volume"], c["head"]))

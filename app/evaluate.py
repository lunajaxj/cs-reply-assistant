# -*- coding: utf-8 -*-
"""Score the chain against the labelled synthetic inquiries.

Labels (expected script category, whether a person must handle it) are written
by the data generator, which knows how each inquiry was made. The numbers show
that the mechanism works on this data set; they say nothing about real traffic.
"""
from __future__ import annotations

from .pipeline import Pipeline


def run(pipeline: Pipeline) -> dict:
    store = pipeline.store
    n = top1 = top3 = 0
    tp = fp = fn = tn = 0
    misses = []
    for qid, label in store.labels.items():
        q = store.inquiries[qid]
        res = pipeline.run(q["text_ko"], q.get("order_no"), q.get("product_code"), use_llm=False)
        cats = [m["category"] for m in res["matches"]]
        got = res["handoff"]["required"]
        want = label["handoff"]
        n += 1
        ok1 = bool(cats) and cats[0] == label["category"]
        top1 += ok1
        top3 += label["category"] in cats
        tp += got and want
        fp += got and not want
        fn += (not got) and want
        tn += (not got) and (not want)
        if not ok1 or got != want:
            misses.append({
                "id": qid, "text_ko": q["text_ko"], "text_zh": q["text_zh"],
                "expected_category": label["category"], "got_category": cats[0] if cats else None,
                "expected_handoff": want, "got_handoff": got,
                "reasons": [r["name"] for r in res["handoff"]["reasons"]],
            })
    return {
        "count": n,
        "retrieval_top1": round(top1 / n, 4) if n else 0,
        "retrieval_top3": round(top3 / n, 4) if n else 0,
        "handoff": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                    "precision": round(tp / (tp + fp), 4) if tp + fp else 1.0,
                    "recall": round(tp / (tp + fn), 4) if tp + fn else 1.0},
        "misses": misses,
    }

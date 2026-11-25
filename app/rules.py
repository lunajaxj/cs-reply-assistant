# -*- coding: utf-8 -*-
"""Step 5: decide whether a person has to handle the inquiry.

Rules are data (``rules.json``) so customer-service leads can switch them on and
off without a code change. A rule that fires does not block the agent; it
replaces the suggested reply with a holding message and puts the case in the
manual queue.

Rule types
----------
keyword          text contains every string in ``all`` and at least one in ``any``
order_not_found  the text names an order number that is not in the data
overdue          the order is more than ``days`` past its expected arrival date
low_confidence   best script score is below ``threshold``
manual_script    best script is marked "manual only" (second net behind keywords)
"""
from __future__ import annotations

from dataclasses import dataclass

from .facts import Facts
from .retriever import Match


@dataclass
class Hit:
    rule_id: str
    name: str
    detail: str

    def to_dict(self) -> dict:
        return self.__dict__


def evaluate(rules: list[dict], text: str, facts: Facts, matches: list[Match]) -> list[Hit]:
    hits: list[Hit] = []
    for r in rules:
        if not r.get("enabled", True):
            continue
        kind = r["type"]
        detail = None
        if kind == "keyword":
            if all(k in text for k in r.get("all", [])):
                found = [k for k in r.get("any", []) if k in text]
                if found or not r.get("any"):
                    detail = "命中关键词：" + "、".join(r.get("all", []) + found[:3])
        elif kind == "order_not_found":
            if facts.missing_orders:
                detail = "查不到订单：" + "、".join(facts.missing_orders)
        elif kind == "overdue":
            if facts.overdue_days > r.get("days", 3):
                detail = f"已超过预计到货日 {facts.overdue_days} 天，仍未签收"
        elif kind == "low_confidence":
            top = matches[0].score if matches else 0.0
            if top < r.get("threshold", 0.15):
                detail = f"话术最高相似度 {top:.2f}，低于阈值 {r.get('threshold', 0.15)}"
        elif kind == "manual_script":
            if matches and matches[0].script.get("manual_only"):
                detail = f"命中话术「{matches[0].script['title']}」属于人工处理类"
        if detail:
            hits.append(Hit(r["id"], r["name"], detail))
    return hits

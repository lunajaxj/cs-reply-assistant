# -*- coding: utf-8 -*-
"""The reply chain, with a timer around every stage.

    extract ids -> complete from data -> retrieve scripts -> rules -> generate
"""
from __future__ import annotations

import time

from . import facts as facts_mod
from . import generator, rules
from .retriever import Retriever
from .store import Store


class Pipeline:
    def __init__(self, store: Store):
        self.store = store
        self.retriever = Retriever(store.scripts)

    def reindex(self) -> None:
        self.retriever.rebuild(self.store.scripts)

    def run(self, text: str, order_no: str | None = None, product_code: str | None = None,
            use_llm: bool = True, top_k: int = 3) -> dict:
        timings: dict[str, float] = {}

        def timed(name, fn):
            t0 = time.perf_counter()
            out = fn()
            timings[name] = round((time.perf_counter() - t0) * 1000, 3)
            return out

        facts = timed("facts", lambda: facts_mod.collect(self.store, text, order_no, product_code))
        matches = timed("retrieve", lambda: self.retriever.search(text, top_k, has_order=bool(facts.order)))
        hits = timed("rules", lambda: rules.evaluate(self.store.rules, text, facts, matches))
        handoff = bool(hits)

        def generate():
            slots_ko, slots_zh = facts_mod.build_slots(facts)
            draft = generator.template_reply(matches, facts, slots_ko, slots_zh, handoff)
            # The model only rewrites replies that are complete and need no person.
            if use_llm and draft["source"] == "template":
                return generator.llm_reply(text, matches, draft, slots_zh) or draft
            return draft

        reply = timed("generate", generate)
        timings["total"] = round(sum(timings.values()), 3)
        return {
            "facts": facts.to_dict(),
            "matches": [m.to_dict() for m in matches],
            "handoff": {"required": handoff, "reasons": [h.to_dict() for h in hits]},
            "reply": reply,
            "timings_ms": timings,
        }

# -*- coding: utf-8 -*-
"""Step 3: find the closest entries in the script library.

The demo uses character-bigram TF-IDF so it runs with no model download and no
GPU. Korean and Chinese need no tokenizer this way. Each example question of a
script is indexed on its own and a script scores as its best example, plus a
small bonus for keyword hits.

To use an embedding model instead, replace this class with one that exposes the
same ``rebuild(scripts)`` and ``search(text, k)``.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_CLEAN = re.compile(r"[^0-9A-Za-zㄱ-ㆎ가-힣一-鿿]+")
_NUMBER = re.compile(r"\d+")


# Polite set phrases that appear in almost every message and say nothing about the topic.
_POLITE = re.compile("부탁드립니다|부탁드려요|부탁합니다|알려주세요|알려 주세요|해주세요|해 주세요|안녕하세요|주문번호")


def tokens(text: str) -> list[str]:
    """Word tokens plus character bigrams inside each word. Digits are folded so
    order numbers do not dominate the similarity."""
    text = _NUMBER.sub("0", _POLITE.sub(" ", text.lower()))
    out: list[str] = []
    for word in _CLEAN.sub(" ", text).split():
        out.append(word)
        out.extend(word[i:i + 2] for i in range(len(word) - 1))
    return out


@dataclass
class Match:
    script: dict
    score: float

    def to_dict(self) -> dict:
        s = self.script
        return {"id": s["id"], "category": s["category"], "category_zh": s["category_zh"],
                "title": s["title"], "manual_only": s.get("manual_only", False),
                "note_zh": s.get("note_zh", ""), "score": round(self.score, 3)}


class Retriever:
    KEYWORD_BONUS = 0.05
    KEYWORD_BONUS_CAP = 0.15
    ORDER_BONUS = 0.1

    def __init__(self, scripts: list[dict]):
        self.rebuild(scripts)

    def rebuild(self, scripts: list[dict]) -> None:
        self.scripts = [s for s in scripts if s.get("enabled", True)]
        docs = []  # (script index, token counts)
        for i, s in enumerate(self.scripts):
            for example in [s["title"], *s.get("examples", [])]:
                docs.append((i, Counter(tokens(example))))
        df: Counter = Counter()
        for _, counts in docs:
            df.update(counts.keys())
        n = len(docs)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self.default_idf = math.log(n + 1) + 1.0
        self.docs = [(i, *self._vector(counts)) for i, counts in docs]

    def _vector(self, counts: Counter) -> tuple[dict, float]:
        vec = {t: (1 + math.log(c)) * self.idf.get(t, self.default_idf) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return vec, norm

    def search(self, text: str, k: int = 3, has_order: bool = False) -> list[Match]:
        """``has_order``: the inquiry is tied to a known order, so scripts that
        answer from order data are preferred over general ones."""
        qvec, qnorm = self._vector(Counter(tokens(text)))
        best: dict[int, float] = {}
        for i, dvec, dnorm in self.docs:
            small, large = (qvec, dvec) if len(qvec) < len(dvec) else (dvec, qvec)
            dot = sum(v * large[t] for t, v in small.items() if t in large)
            score = dot / (qnorm * dnorm)
            if score > best.get(i, 0.0):
                best[i] = score
        out = []
        for i, score in best.items():
            s = self.scripts[i]
            hits = sum(1 for kw in s.get("keywords", []) if kw and kw in text)
            score += min(self.KEYWORD_BONUS_CAP, hits * self.KEYWORD_BONUS)
            if has_order and "order" in s.get("requires", []):
                score += self.ORDER_BONUS
            score = min(1.0, score)
            out.append(Match(s, score))
        out.sort(key=lambda m: m.score, reverse=True)
        return out[:k]

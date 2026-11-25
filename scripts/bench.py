# -*- coding: utf-8 -*-
"""Per-stage timing of the reply chain over every demo inquiry.

    python scripts/bench.py [rounds]

Template mode only, so the numbers are the cost of everything around the model
call (id extraction, data lookup, retrieval, rules).
"""
import io
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from app.pipeline import Pipeline  # noqa: E402
from app.store import Store  # noqa: E402

rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 20
store = Store(local_dir=None)
pipeline = Pipeline(store)
samples: dict[str, list[float]] = {}
for _ in range(rounds):
    for q in store.inquiries.values():
        res = pipeline.run(q["text_ko"], q.get("order_no"), q.get("product_code"), use_llm=False)
        for stage, ms in res["timings_ms"].items():
            samples.setdefault(stage, []).append(ms)

print(f"{len(store.inquiries)} inquiries x {rounds} rounds")
print(f"{'stage':<10}{'mean ms':>10}{'p95 ms':>10}")
for stage, xs in samples.items():
    xs.sort()
    print(f"{stage:<10}{statistics.mean(xs):>10.3f}{xs[int(len(xs) * 0.95) - 1]:>10.3f}")

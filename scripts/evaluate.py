# -*- coding: utf-8 -*-
"""Print retrieval and handoff metrics on the labelled synthetic inquiries.

    python scripts/evaluate.py
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from app import evaluate  # noqa: E402
from app.pipeline import Pipeline  # noqa: E402
from app.store import Store  # noqa: E402

res = evaluate.run(Pipeline(Store(local_dir=None)))
h = res["handoff"]
print(f"inquiries        {res['count']}")
print(f"retrieval top-1  {res['retrieval_top1']:.1%}")
print(f"retrieval top-3  {res['retrieval_top3']:.1%}")
print(f"handoff          precision {h['precision']:.1%}  recall {h['recall']:.1%}  "
      f"(tp {h['tp']} fp {h['fp']} fn {h['fn']} tn {h['tn']})")
for m in res["misses"]:
    print(f"  miss {m['id']}  want {m['expected_category']}/{m['expected_handoff']}  "
          f"got {m['got_category']}/{m['got_handoff']} {m['reasons']}  {m['text_ko']}")

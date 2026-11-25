# -*- coding: utf-8 -*-
"""In-memory data store for the demo.

Everything is read from ``demo_data/*.json`` (synthetic, produced by
``scripts/make_demo_data.py``). Edits made in the UI (script library, rule
switches) are written to ``local/`` so the committed demo data never changes.
"""
from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "demo_data"
LOCAL_DIR = ROOT / "local"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Store:
    def __init__(self, data_dir: Path = DATA_DIR, local_dir: Path | None = LOCAL_DIR):
        self.data_dir = Path(data_dir)
        self.local_dir = Path(local_dir) if local_dir else None
        self.lock = threading.RLock()

        meta = _load(self.data_dir / "meta.json")
        self.today = date.fromisoformat(meta["demo_date"])
        self.meta = meta

        self.products = {p["code"]: p for p in _load(self.data_dir / "products.json")}
        self.orders = {o["order_no"]: o for o in _load(self.data_dir / "orders.json")}
        self.inventory = {i["product_code"]: i for i in _load(self.data_dir / "inventory.json")}
        self.arrivals = _load(self.data_dir / "arrivals.json")
        self.inquiries = {q["id"]: dict(q, state="open") for q in _load(self.data_dir / "inquiries.json")}
        self.labels = {x["id"]: x for x in _load(self.data_dir / "eval_labels.json")}

        self.scripts = self._load_editable("scripts.json")
        self.rules = self._load_editable("rules.json")
        self.customs_index = {o["customs_no"]: o["order_no"] for o in self.orders.values()}

    # ---- editable collections -------------------------------------------------
    def _load_editable(self, name: str) -> list[dict]:
        if self.local_dir and (self.local_dir / name).exists():
            return _load(self.local_dir / name)
        return _load(self.data_dir / name)

    def _save_editable(self, name: str, rows: list[dict]) -> None:
        if not self.local_dir:
            return
        self.local_dir.mkdir(exist_ok=True)
        (self.local_dir / name).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_scripts(self) -> None:
        self._save_editable("scripts.json", self.scripts)

    def save_rules(self) -> None:
        self._save_editable("rules.json", self.rules)

    def script_by_id(self, script_id: str) -> dict | None:
        return next((s for s in self.scripts if s["id"] == script_id), None)

    def next_script_id(self) -> str:
        nums = [int(s["id"][1:]) for s in self.scripts if s["id"][1:].isdigit()]
        return f"S{(max(nums) if nums else 0) + 1:02d}"

    # ---- lookups ----------------------------------------------------------------
    def arrivals_for(self, product_code: str) -> list[dict]:
        return [a for a in self.arrivals if a["product_code"] == product_code]

    def product_by_name(self, text: str) -> dict | None:
        """Longest product name mentioned in the text, if any."""
        hits = [p for p in self.products.values() if p["name_ko"] in text]
        return max(hits, key=lambda p: len(p["name_ko"])) if hits else None

    def search(self, q: str) -> dict:
        """Free lookup used by the side panel: order no / product code / customs no / name."""
        q = q.strip()
        orders, products = [], []
        if not q:
            return {"orders": orders, "products": products}
        if q in self.orders:
            orders.append(self.orders[q])
        elif q in self.customs_index:
            orders += [o for o in self.orders.values() if o["customs_no"] == q]
        else:
            orders += [o for o in self.orders.values() if q in o["order_no"]][:10]
        up = q.upper()
        for p in self.products.values():
            if up == p["code"] or q in p["name_ko"] or q in p["name_zh"]:
                products.append(p)
        return {"orders": orders, "products": products[:10]}

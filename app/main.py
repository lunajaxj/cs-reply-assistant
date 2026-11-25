# -*- coding: utf-8 -*-
"""HTTP API and static web workbench."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import evaluate, generator
from .const import STATUS_ZH
from .pipeline import Pipeline
from .store import Store

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class ReplyIn(BaseModel):
    inquiry_id: str | None = None
    text: str | None = None
    order_no: str | None = None
    product_code: str | None = None
    use_llm: bool = True


class StateIn(BaseModel):
    state: str = Field(pattern="^(open|replied|handoff)$")
    reply: str | None = None


class ScriptIn(BaseModel):
    category: str
    category_zh: str
    title: str
    examples: list[str] = []
    keywords: list[str] = []
    requires: list[str] = []
    reply_ko: str
    reply_zh: str = ""
    note_zh: str = ""
    manual_only: bool = False
    enabled: bool = True


class RuleIn(BaseModel):
    enabled: bool


def create_app(store: Store | None = None) -> FastAPI:
    store = store or Store()
    pipeline = Pipeline(store)
    app = FastAPI(title="cs-reply-assistant (demo)")

    @app.get("/api/health")
    def health():
        cfg = generator.llm_config()
        return {"ok": True, "demo_date": store.today.isoformat(),
                "generator": "llm" if cfg else "template", "model": cfg["model"] if cfg else None,
                "counts": {"orders": len(store.orders), "products": len(store.products),
                           "scripts": len(store.scripts), "inquiries": len(store.inquiries)},
                "status_zh": STATUS_ZH}

    # ---- inquiries ------------------------------------------------------------
    @app.get("/api/inquiries")
    def inquiries():
        rows = sorted(store.inquiries.values(), key=lambda q: q["created_at"], reverse=True)
        return {"items": rows, "states": Counter(q["state"] for q in rows)}

    @app.post("/api/reply")
    def reply(body: ReplyIn):
        if body.inquiry_id:
            q = store.inquiries.get(body.inquiry_id)
            if not q:
                raise HTTPException(404, "inquiry not found")
            text, order_no, product_code = q["text_ko"], q.get("order_no"), q.get("product_code")
        elif body.text and body.text.strip():
            text, order_no, product_code = body.text.strip(), body.order_no, body.product_code
        else:
            raise HTTPException(422, "inquiry_id or text is required")
        return pipeline.run(text, order_no, product_code, use_llm=body.use_llm)

    @app.post("/api/inquiries/{qid}/state")
    def set_state(qid: str, body: StateIn):
        q = store.inquiries.get(qid)
        if not q:
            raise HTTPException(404, "inquiry not found")
        with store.lock:
            q["state"] = body.state
            q["sent_reply"] = body.reply if body.state == "replied" else None
        return q

    # ---- lookups ---------------------------------------------------------------
    @app.get("/api/lookup")
    def lookup(q: str = ""):
        found = store.search(q)
        return {
            "orders": found["orders"],
            "products": [dict(p, inventory=store.inventory.get(p["code"]),
                              arrivals=store.arrivals_for(p["code"])) for p in found["products"]],
        }

    # ---- script library ----------------------------------------------------------
    @app.get("/api/scripts")
    def scripts():
        return {"items": store.scripts}

    @app.post("/api/scripts")
    def add_script(body: ScriptIn):
        with store.lock:
            row = {"id": store.next_script_id(), **body.model_dump()}
            store.scripts.append(row)
            store.save_scripts()
            pipeline.reindex()
        return row

    @app.put("/api/scripts/{sid}")
    def update_script(sid: str, body: ScriptIn):
        with store.lock:
            row = store.script_by_id(sid)
            if not row:
                raise HTTPException(404, "script not found")
            row.update(body.model_dump())
            store.save_scripts()
            pipeline.reindex()
        return row

    @app.delete("/api/scripts/{sid}")
    def delete_script(sid: str):
        with store.lock:
            row = store.script_by_id(sid)
            if not row:
                raise HTTPException(404, "script not found")
            store.scripts.remove(row)
            store.save_scripts()
            pipeline.reindex()
        return {"deleted": sid}

    # ---- handoff rules -----------------------------------------------------------
    @app.get("/api/rules")
    def rules():
        return {"items": store.rules}

    @app.patch("/api/rules/{rid}")
    def toggle_rule(rid: str, body: RuleIn):
        with store.lock:
            row = next((r for r in store.rules if r["id"] == rid), None)
            if not row:
                raise HTTPException(404, "rule not found")
            row["enabled"] = body.enabled
            store.save_rules()
        return row

    # ---- evaluation ----------------------------------------------------------------
    @app.get("/api/eval")
    def run_eval():
        return evaluate.run(pipeline)

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()

# -*- coding: utf-8 -*-
"""Step 4: write the reply.

Two modes:

* template (default) - the best script is filled with verified data. Runs
  offline and is fully deterministic, which is what the tests and the demo use.
* llm - if ``LLM_BASE_URL`` and ``LLM_MODEL`` are set, an OpenAI-compatible chat
  endpoint rewrites the reply from the same scripts and data. Any failure falls
  back to the template result.
"""
from __future__ import annotations

import json
import os
import re

import httpx

from .facts import Facts
from .retriever import Match

ASK_ORDER_KO = ("안녕하세요, 고객님. 문의 주셔서 감사합니다.\n"
                "정확한 확인을 위해 주문번호를 알려주시면 바로 확인해 드리겠습니다. 감사합니다.")
ASK_ORDER_ZH = "您好，感谢咨询。\n为了准确核实，请提供订单号，我们马上为您查询。谢谢。"

ASK_PRODUCT_KO = ("안녕하세요, 고객님. 문의 주셔서 감사합니다.\n"
                  "문의하신 상품명 또는 상품코드를 알려주시면 바로 확인해 드리겠습니다. 감사합니다.")
ASK_PRODUCT_ZH = "您好，感谢咨询。\n请告知商品名称或商品编码，我们马上为您确认。谢谢。"

HOLDING_KO = ("안녕하세요, 고객님. 불편을 드려 죄송합니다.\n"
              "문의하신 내용은 담당자가 확인한 뒤 빠르게 안내드리겠습니다. "
              "조금만 기다려 주시면 감사하겠습니다.")
HOLDING_ZH = "您好，给您带来不便非常抱歉。\n您咨询的内容将由专人核实后尽快答复，请稍候。"

_SLOT = re.compile(r"\{(\w+)\}")


def render(template: str, slots: dict) -> str:
    """Fill ``{slot}`` markers. Unknown slots become empty so a script edited in
    the UI can never break a reply; leftover blank lines are removed."""
    text = _SLOT.sub(lambda m: str(slots.get(m.group(1), "")), template)
    lines = [re.sub(r"[ \t]{2,}", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def _missing(script: dict, facts: Facts) -> str | None:
    for need in script.get("requires", []):
        if need == "order" and not facts.order:
            return "order"
        if need == "product" and not facts.product:
            return "product"
    return None


def template_reply(matches: list[Match], facts: Facts, slots_ko: dict, slots_zh: dict,
                   handoff: bool) -> dict:
    script = matches[0].script if matches else None
    if handoff:
        if script and script.get("manual_only"):
            return {"ko": render(script["reply_ko"], slots_ko), "zh": render(script["reply_zh"], slots_zh),
                    "source": "holding", "script_id": script["id"]}
        return {"ko": HOLDING_KO, "zh": HOLDING_ZH, "source": "holding", "script_id": None}
    if script is None:
        return {"ko": HOLDING_KO, "zh": HOLDING_ZH, "source": "holding", "script_id": None}
    need = _missing(script, facts)
    if need == "order":
        return {"ko": ASK_ORDER_KO, "zh": ASK_ORDER_ZH, "source": "ask_order", "script_id": script["id"]}
    if need == "product":
        return {"ko": ASK_PRODUCT_KO, "zh": ASK_PRODUCT_ZH, "source": "ask_product", "script_id": script["id"]}
    return {"ko": render(script["reply_ko"], slots_ko), "zh": render(script["reply_zh"], slots_zh),
            "source": "template", "script_id": script["id"]}


# ---- optional LLM mode ----------------------------------------------------------

SYSTEM_PROMPT = """你是韩国电商店铺的客服回复助手。请根据【买家咨询】【参考话术】【已核实数据】写一条回复。
要求：
1. 用韩语敬语（합니다체），3 到 5 句，开头问候，结尾致谢。
2. 订单状态、日期、运单号、库存数量只能使用【已核实数据】里的内容，没有的数据不要编。
3. 不承诺退款、赔偿、补发，也不承诺【已核实数据】以外的时效。
4. 只输出 JSON：{"ko": "韩语回复", "zh": "给客服看的中文对照"}"""


def llm_config() -> dict | None:
    base, model = os.getenv("LLM_BASE_URL"), os.getenv("LLM_MODEL")
    if not (base and model):
        return None
    return {"base_url": base.rstrip("/"), "model": model, "api_key": os.getenv("LLM_API_KEY", ""),
            "timeout": float(os.getenv("LLM_TIMEOUT", "30"))}


def build_messages(text: str, matches: list[Match], draft: dict, slots_zh: dict) -> list[dict]:
    refs = "\n\n".join(f"[{m.script['title']}]\n{m.script['reply_ko']}" for m in matches[:3])
    verified = "\n".join(f"- {k}: {v}" for k, v in slots_zh.items() if v) or "（无）"
    user = (f"【买家咨询】\n{text}\n\n【参考话术】\n{refs}\n\n【已核实数据】\n{verified}\n\n"
            f"【按话术直接填充的草稿，可在此基础上调整语气】\n{draft['ko']}")
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def _post_chat(cfg: dict, messages: list[dict]) -> str:
    headers = {"Authorization": f"Bearer {cfg['api_key']}"} if cfg["api_key"] else {}
    resp = httpx.post(f"{cfg['base_url']}/chat/completions", headers=headers, timeout=cfg["timeout"],
                      json={"model": cfg["model"], "messages": messages, "temperature": 0.3})
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def parse_llm_json(content: str) -> dict | None:
    m = re.search(r"\{.*\}", content, flags=re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(data.get("ko"), str) and data["ko"].strip():
        return {"ko": data["ko"].strip(), "zh": str(data.get("zh", "")).strip()}
    return None


def llm_reply(text: str, matches: list[Match], draft: dict, slots_zh: dict) -> dict | None:
    """Returns None when the LLM is not configured or the call fails."""
    cfg = llm_config()
    if not cfg:
        return None
    try:
        parsed = parse_llm_json(_post_chat(cfg, build_messages(text, matches, draft, slots_zh)))
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None
    if not parsed:
        return None
    return {**parsed, "source": "llm", "script_id": draft.get("script_id")}

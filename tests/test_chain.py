# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient

from app import evaluate, facts, generator
from app.main import create_app
from app.pipeline import Pipeline
from app.retriever import Retriever
from app.store import Store


@pytest.fixture(scope="module")
def store():
    return Store(local_dir=None)


@pytest.fixture(scope="module")
def pipeline(store):
    return Pipeline(store)


@pytest.fixture()
def client():
    return TestClient(create_app(Store(local_dir=None)))


def order_with(store, status):
    return next(o for o in store.orders.values() if o["status"] == status
                and (status == "배송완료" or o["eta"] >= store.today.isoformat()))


# ---- facts --------------------------------------------------------------------

def test_extract_ids_finds_each_identifier_once():
    ids = facts.extract_ids("주문번호 20261110-12345, 20261110-12345 / HA-10234 / P123456789012 입니다")
    assert ids.order_nos == ["20261110-12345"]
    assert ids.product_codes == ["HA-10234"]
    assert ids.customs_nos == ["P123456789012"]


def test_extract_ids_ignores_longer_digit_runs():
    assert facts.extract_ids("전화 0102026111012345678").order_nos == []


def test_text_order_wins_over_attached_order(store):
    a, b = list(store.orders)[:2]
    f = facts.collect(store, f"주문번호 {a} 확인 부탁드립니다", order_no=b)
    assert f.order["order_no"] == a


def test_unknown_order_is_reported_missing(store):
    f = facts.collect(store, "주문번호 20261101-00000 확인해 주세요")
    assert f.order is None and f.missing_orders == ["20261101-00000"]


def test_customs_number_resolves_to_order(store):
    o = next(iter(store.orders.values()))
    f = facts.collect(store, f"통관부호 {o['customs_no']} 로 조회해 주세요")
    assert f.order["customs_no"] == o["customs_no"]


def test_customs_number_is_masked_in_reply(store, pipeline):
    o = order_with(store, "통관중")
    res = pipeline.run(f"통관 진행 상황 알려주세요. {o['order_no']}", use_llm=False)
    assert o["customs_no"] not in res["reply"]["ko"]
    assert facts.mask_customs(o["customs_no"]) in res["reply"]["ko"]


# ---- retrieval ------------------------------------------------------------------

@pytest.mark.parametrize("text,category", [
    ("택배가 아직도 안 왔어요. 어디쯤인가요?", "shipping_status"),
    ("세관 통관이 너무 오래 걸려요", "customs"),
    ("환불 받고 싶은데요", "return_refund"),
    ("합배송 가능한가요", "combined_shipping"),
])
def test_retriever_picks_expected_category(store, text, category):
    assert Retriever(store.scripts).search(text, 1)[0].script["category"] == category


def test_disabled_script_is_not_retrieved(store):
    scripts = [dict(s, enabled=s["category"] != "customs") for s in store.scripts]
    cats = [m.script["category"] for m in Retriever(scripts).search("통관 진행 상황", 5)]
    assert "customs" not in cats


# ---- generation ---------------------------------------------------------------------

def test_shipping_reply_uses_order_data(store, pipeline):
    o = order_with(store, "국내배송중")
    res = pipeline.run(f"{o['order_no']} 배송 어디까지 왔나요?", use_llm=False)
    assert res["handoff"]["required"] is False
    assert res["reply"]["source"] == "template"
    assert o["order_no"] in res["reply"]["ko"] and o["tracking_no"] in res["reply"]["ko"]
    assert "{" not in res["reply"]["ko"] and "{" not in res["reply"]["zh"]


def test_missing_order_asks_for_order_number(pipeline):
    res = pipeline.run("택배 언제 도착해요?", use_llm=False)
    assert res["reply"]["source"] == "ask_order"
    assert res["handoff"]["required"] is False


def test_stock_reply_reflects_inventory(store, pipeline):
    code, inv = next((c, i) for c, i in store.inventory.items() if i["on_hand"] - i["reserved"] > 0)
    res = pipeline.run(f"상품코드 {code} 재고 있나요?", use_llm=False)
    assert f"{inv['on_hand'] - inv['reserved']}개" in res["reply"]["ko"]


def test_render_drops_unknown_slots_and_blank_lines():
    assert generator.render("가 {nope}\n{nope}\n나", {}) == "가\n나"


# ---- handoff rules ----------------------------------------------------------------------

@pytest.mark.parametrize("text,rule", [
    ("환불해 주세요", "R1"),
    ("다른 색상으로 교환 가능한가요?", "R2"),
    ("주문 취소하고 싶어요", "R3"),
    ("받아보니 파손되어 있어요", "R4"),
    ("소비자원에 신고하겠습니다", "R5"),
    ("배송완료라는데 못 받았어요", "R6"),
    ("주문번호 20261101-00000 확인 부탁드립니다", "R7"),
])
def test_rule_fires(pipeline, text, rule):
    res = pipeline.run(text, use_llm=False)
    assert rule in [r["rule_id"] for r in res["handoff"]["reasons"]]
    assert res["reply"]["source"] == "holding"


def test_overdue_order_goes_to_a_person(store, pipeline):
    late = next(o for o in store.orders.values()
                if o["status"] != "배송완료" and o["eta"] < "2026-11-16")
    res = pipeline.run(f"{late['order_no']} 언제 오나요?", use_llm=False)
    assert "R8" in [r["rule_id"] for r in res["handoff"]["reasons"]]


def test_disabled_rule_does_not_fire(store):
    s = Store(local_dir=None)
    for r in s.rules:
        r["enabled"] = False
    res = Pipeline(s).run("환불해 주세요", use_llm=False)
    assert res["handoff"]["required"] is False


# ---- llm mode (endpoint is stubbed) --------------------------------------------------------

def test_llm_rewrites_only_complete_replies(store, pipeline, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LLM_MODEL", "stub")
    calls = []

    def fake(cfg, messages):
        calls.append(messages)
        return '```json\n{"ko": "안녕하세요, 고객님. 확인해 드렸습니다.", "zh": "已为您确认。"}\n```'

    monkeypatch.setattr(generator, "_post_chat", fake)
    o = order_with(store, "국내배송중")
    res = pipeline.run(f"{o['order_no']} 배송 어디까지 왔나요?")
    assert res["reply"]["source"] == "llm" and len(calls) == 1
    assert o["order_no"] in calls[0][1]["content"]          # verified data is in the prompt
    assert o["customs_no"] not in calls[0][1]["content"]    # the full customs number is not

    pipeline.run("환불해 주세요")           # handoff: the model is not asked
    pipeline.run("택배 언제 도착해요?")      # data missing: the model is not asked
    assert len(calls) == 1


def test_llm_failure_falls_back_to_template(store, pipeline, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LLM_MODEL", "stub")
    monkeypatch.setattr(generator, "_post_chat", lambda cfg, messages: "not json")
    o = order_with(store, "국내배송중")
    assert pipeline.run(f"{o['order_no']} 배송 어디까지 왔나요?")["reply"]["source"] == "template"


# ---- whole data set ----------------------------------------------------------------------------

def test_evaluation_thresholds(pipeline):
    res = evaluate.run(pipeline)
    assert res["count"] >= 60
    assert res["retrieval_top1"] >= 0.9
    assert res["retrieval_top3"] >= 0.98
    assert res["handoff"]["recall"] == 1.0
    assert res["handoff"]["precision"] >= 0.95


# ---- api -----------------------------------------------------------------------------------------

def test_api_reply_and_state(client):
    items = client.get("/api/inquiries").json()["items"]
    qid = items[0]["id"]
    res = client.post("/api/reply", json={"inquiry_id": qid, "use_llm": False}).json()
    assert res["reply"]["ko"]
    out = client.post(f"/api/inquiries/{qid}/state", json={"state": "replied", "reply": res["reply"]["ko"]}).json()
    assert out["state"] == "replied"
    assert client.post(f"/api/inquiries/{qid}/state", json={"state": "bogus"}).status_code == 422
    assert client.post("/api/reply", json={}).status_code == 422
    assert client.post("/api/reply", json={"inquiry_id": "nope"}).status_code == 404


def test_api_script_edit_changes_retrieval(client):
    text = "포인트 적립은 어떻게 되나요?"
    before = client.post("/api/reply", json={"text": text, "use_llm": False}).json()
    assert before["matches"][0]["category"] != "points"
    new = client.post("/api/scripts", json={
        "category": "points", "category_zh": "积分", "title": "积分说明",
        "examples": ["포인트 적립은 어떻게 되나요?", "적립금은 언제 들어오나요?"],
        "reply_ko": "안녕하세요, 고객님. 포인트는 구매 확정 후 적립됩니다.", "reply_zh": "积分在确认收货后到账。",
    }).json()
    after = client.post("/api/reply", json={"text": text, "use_llm": False}).json()
    assert after["matches"][0]["id"] == new["id"]
    assert after["reply"]["ko"].endswith("적립됩니다.")
    assert client.delete(f"/api/scripts/{new['id']}").status_code == 200
    assert client.delete(f"/api/scripts/{new['id']}").status_code == 404


def test_api_rule_toggle_and_lookup(client):
    assert client.patch("/api/rules/R1", json={"enabled": False}).json()["enabled"] is False
    order = client.get("/api/inquiries").json()["items"]
    o = next(q["order_no"] for q in order if q["order_no"])
    found = client.get("/api/lookup", params={"q": o}).json()
    assert found["orders"][0]["order_no"] == o
    assert client.get("/api/lookup", params={"q": "청소기"}).json()["products"][0]["inventory"]
    assert client.get("/").status_code == 200

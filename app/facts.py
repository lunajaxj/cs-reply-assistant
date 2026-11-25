# -*- coding: utf-8 -*-
"""Step 1 and 2 of the reply chain: pull hard identifiers out of the inquiry
text and complete them from the data store.

The point of doing this before generation is that order status, dates and
stock numbers in a reply come from data, never from the language model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .const import CUSTOMS_NO_RE, ORDER_NO_RE, PRODUCT_CODE_RE, STATUS_ZH
from .store import Store


@dataclass
class Ids:
    order_nos: list[str] = field(default_factory=list)
    product_codes: list[str] = field(default_factory=list)
    customs_nos: list[str] = field(default_factory=list)


@dataclass
class Facts:
    ids: Ids
    order: dict | None = None
    product: dict | None = None
    inventory: dict | None = None
    arrivals: list[dict] = field(default_factory=list)
    missing_orders: list[str] = field(default_factory=list)
    overdue_days: int = 0  # days past the expected arrival date, not yet delivered

    def to_dict(self) -> dict:
        return {
            "ids": self.ids.__dict__,
            "order": self.order,
            "product": self.product,
            "inventory": self.inventory,
            "arrivals": self.arrivals,
            "missing_orders": self.missing_orders,
            "overdue_days": self.overdue_days,
        }


def _unique(seq):
    return list(dict.fromkeys(seq))


def extract_ids(text: str) -> Ids:
    return Ids(
        order_nos=_unique(ORDER_NO_RE.findall(text)),
        product_codes=_unique(PRODUCT_CODE_RE.findall(text)),
        customs_nos=_unique(CUSTOMS_NO_RE.findall(text)),
    )


def collect(store: Store, text: str, order_no: str | None = None,
            product_code: str | None = None) -> Facts:
    """``order_no`` / ``product_code`` are what the shop back office attaches to
    an inquiry; identifiers written in the text take priority over them."""
    ids = extract_ids(text)
    facts = Facts(ids=ids)

    candidates = list(ids.order_nos)
    for cn in ids.customs_nos:
        if cn in store.customs_index:
            candidates.append(store.customs_index[cn])
    if order_no:
        candidates.append(order_no)
    for no in _unique(candidates):
        if no in store.orders:
            facts.order = facts.order or store.orders[no]
        else:
            facts.missing_orders.append(no)

    codes = list(ids.product_codes)
    if product_code:
        codes.append(product_code)
    for code in codes:
        if code in store.products:
            facts.product = store.products[code]
            break
    if facts.product is None:
        facts.product = store.product_by_name(text)
    if facts.product is None and facts.order:
        facts.product = store.products.get(facts.order["product_code"])

    if facts.product:
        code = facts.product["code"]
        facts.inventory = store.inventory.get(code)
        facts.arrivals = store.arrivals_for(code)

    if facts.order and facts.order["status"] != "배송완료":
        eta = date.fromisoformat(facts.order["eta"])
        facts.overdue_days = max(0, (store.today - eta).days)
    return facts


# ---- slots: the values that reply templates may reference --------------------

def _ko_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.month}월 {d.day}일"


def _zh_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.month}月{d.day}日"


def mask_customs(no: str) -> str:
    return no[:5] + "****" + no[-4:]


_PROGRESS_KO = {
    "결제완료": "결제가 확인되어 출고 준비를 시작한 상태입니다",
    "상품준비중": "현재 상품 준비 중이며 곧 해외 물류센터에서 출고될 예정입니다",
    "해외배송중": "현재 해외에서 한국으로 배송 중입니다",
    "통관중": "현재 한국 세관에서 통관 절차가 진행 중입니다",
    "국내배송중": "통관이 완료되어 현재 국내 택배로 배송 중입니다",
}
_PROGRESS_ZH = {
    "결제완료": "已确认付款，开始备货",
    "상품준비중": "正在备货，即将从海外仓发出",
    "해외배송중": "正在从海外运往韩国",
    "통관중": "正在韩国海关办理清关",
    "국내배송중": "已完成清关，正由韩国境内快递派送",
}


def build_slots(facts: Facts) -> tuple[dict, dict]:
    """Return (korean slots, chinese slots). Missing data simply yields no key;
    the generator checks a script's ``requires`` before rendering."""
    ko: dict[str, str] = {"product_ref": "문의하신 상품"}
    zh: dict[str, str] = {"product_ref": "您咨询的商品"}

    o = facts.order
    if o:
        ko["order_no"] = zh["order_no"] = o["order_no"]
        ko["status"] = o["status"]
        zh["status"] = STATUS_ZH[o["status"]]
        if o["status"] == "배송완료":
            ko["progress_line"] = f"{_ko_date(o['delivered_at'])}에 배송완료 처리된 것으로 확인됩니다"
            zh["progress_line"] = f"系统显示已于 {_zh_date(o['delivered_at'])} 签收"
            ko["eta_line"] = zh["eta_line"] = ""
        else:
            ko["progress_line"] = _PROGRESS_KO[o["status"]]
            zh["progress_line"] = _PROGRESS_ZH[o["status"]]
            ko["eta_line"] = f"예상 도착일은 {_ko_date(o['eta'])}경입니다."
            zh["eta_line"] = f"预计 {_zh_date(o['eta'])} 前后送达。"
        if o.get("tracking_no"):
            ko["tracking_line"] = f"운송장번호는 {o['carrier']} {o['tracking_no']}입니다."
            zh["tracking_line"] = f"运单号：{o['carrier']} {o['tracking_no']}。"
        else:
            ko["tracking_line"] = "운송장번호는 출고 후 바로 안내드리겠습니다."
            zh["tracking_line"] = "运单号将在发货后告知。"
        masked = mask_customs(o["customs_no"])
        ko["customs_line"] = f"등록하신 개인통관고유부호는 {masked}로 확인됩니다."
        zh["customs_line"] = f"登记的个人通关号为 {masked}。"

    p = facts.product
    if p:
        ko["product_name"] = p["name_ko"]
        zh["product_name"] = p["name_zh"]
        ko["product_ref"] = f"문의하신 {p['name_ko']}"
        zh["product_ref"] = f"您咨询的{p['name_zh']}"
        inv = facts.inventory
        if inv:
            free = inv["on_hand"] - inv["reserved"]
            if free > 0:
                ko["stock_line"] = f"현재 재고 {free}개가 있어 주문하시면 영업일 기준 1~2일 내 출고됩니다."
                zh["stock_line"] = f"现有可用库存 {free} 件，下单后 1 至 2 个工作日内发货。"
            elif inv.get("next_arrival_date"):
                ko["stock_line"] = (f"현재 일시 품절 상태이며, {_ko_date(inv['next_arrival_date'])}경 "
                                    f"{inv['next_arrival_qty']}개가 재입고될 예정입니다.")
                zh["stock_line"] = (f"目前暂时缺货，预计 {_zh_date(inv['next_arrival_date'])} 前后"
                                    f"到货 {inv['next_arrival_qty']} 件。")
            else:
                ko["stock_line"] = "현재 품절 상태이며 재입고 일정은 아직 정해지지 않았습니다."
                zh["stock_line"] = "目前缺货，补货时间尚未确定。"
    return ko, zh

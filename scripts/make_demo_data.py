# -*- coding: utf-8 -*-
"""Generate the synthetic demo data set.

    python scripts/make_demo_data.py

Everything here is made up: products, buyers, orders, customs numbers, tracking
numbers and inquiries. The output is deterministic (fixed seed and a fixed
"demo date"), so tests and the evaluation page always see the same data.
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "demo_data"
DEMO_DATE = date(2026, 11, 20)
SEED = 20261120
rng = random.Random(SEED)

# ---------------------------------------------------------------- products ---
PRODUCTS = [
    ("HA", "무선 핸디 청소기", "无线手持吸尘器", 59000),
    ("HA", "미니 가습기", "迷你加湿器", 23000),
    ("HA", "LED 무드등", "LED 氛围灯", 18000),
    ("HA", "휴대용 선풍기", "便携风扇", 15000),
    ("EL", "블루투스 이어폰", "蓝牙耳机", 39000),
    ("EL", "노트북 거치대", "笔记本支架", 27000),
    ("EL", "차량용 핸드폰 거치대", "车载手机支架", 14000),
    ("EL", "스마트 체중계", "智能体重秤", 32000),
    ("KT", "스테인리스 텀블러", "不锈钢保温杯", 19000),
    ("KT", "실리콘 조리도구 세트", "硅胶厨具套装", 26000),
    ("KT", "커피 그라인더", "咖啡研磨机", 45000),
    ("KT", "접이식 도시락통", "折叠饭盒", 12000),
    ("OD", "접이식 캠핑 의자", "折叠露营椅", 34000),
    ("OD", "방수 등산 배낭", "防水登山包", 52000),
    ("OD", "요가 매트", "瑜伽垫", 21000),
    ("OD", "캠핑용 랜턴", "露营灯", 29000),
    ("FS", "남성 경량 패딩 조끼", "男士轻薄羽绒马甲", 48000),
    ("FS", "여성 니트 가디건", "女士针织开衫", 43000),
    ("FS", "아동용 우비", "儿童雨衣", 17000),
    ("FS", "기모 트레이닝 바지", "加绒运动裤", 31000),
    ("PT", "반려동물 자동 급식기", "宠物自动喂食器", 68000),
    ("PT", "고양이 스크래처", "猫抓板", 16000),
    ("HL", "전동 칫솔", "电动牙刷", 36000),
    ("HL", "메모리폼 베개", "记忆棉枕头", 28000),
]

SURNAMES = "김이박최정강조윤장임한오서신권"
GIVEN = ["민준", "서연", "지우", "하준", "서윤", "도윤", "지민", "예준", "수아", "지호",
         "유진", "현우", "은지", "태현", "소연", "준영", "미경", "성민", "하은", "동현"]
CARRIERS = ["CJ대한통운", "한진택배", "롯데택배"]
CHANNELS = ["店铺 A", "店铺 B", "店铺 C"]


def make_products():
    used, rows = set(), []
    for cat, ko, zh, price in PRODUCTS:
        while True:
            code = f"{cat}-{rng.randint(10000, 99999)}"
            if code not in used:
                used.add(code)
                break
        rows.append({"code": code, "name_ko": ko, "name_zh": zh, "category": cat, "price_krw": price})
    return rows


def masked_name():
    return rng.choice(SURNAMES) + "*" + rng.choice(GIVEN)[-1]


def make_orders(products, n=160):
    rows, used = [], set()
    for _ in range(n):
        age = rng.randint(0, 30)
        ordered = DEMO_DATE - timedelta(days=age)
        eta_days = rng.randint(9, 12)
        eta = ordered + timedelta(days=eta_days)
        delayed = age >= eta_days + 4 and rng.random() < 0.22
        if delayed:
            status = rng.choice(["해외배송중", "통관중", "국내배송중"])
        elif age == 0:
            status = "결제완료"
        elif age <= 2:
            status = "상품준비중"
        elif age <= 5:
            status = "해외배송중"
        elif age <= 7:
            status = "통관중"
        elif age < eta_days:
            status = "국내배송중"
        else:
            status = "배송완료"
        while True:
            no = f"{ordered:%Y%m%d}-{rng.randint(10000, 99999)}"
            if no not in used:
                used.add(no)
                break
        p = rng.choice(products)
        qty = rng.choice([1, 1, 1, 2, 3])
        shipped = status in ("해외배송중", "통관중", "국내배송중", "배송완료")
        rows.append({
            "order_no": no,
            "buyer": masked_name(),
            "channel": rng.choice(CHANNELS),
            "product_code": p["code"],
            "qty": qty,
            "amount_krw": p["price_krw"] * qty,
            "status": status,
            "ordered_at": ordered.isoformat(),
            "eta": eta.isoformat(),
            "delivered_at": (eta - timedelta(days=rng.randint(0, 1))).isoformat() if status == "배송완료" else None,
            "carrier": rng.choice(CARRIERS) if shipped else None,
            "tracking_no": str(rng.randint(10 ** 11, 10 ** 12 - 1)) if shipped else None,
            "customs_no": "P" + str(rng.randint(10 ** 11, 10 ** 12 - 1)),
            "delayed": delayed,
        })
    rows.sort(key=lambda o: o["order_no"], reverse=True)
    return rows


def make_inventory(products):
    inv, arrivals = [], []
    for p in products:
        out_of_stock = rng.random() < 0.3
        on_hand = 0 if out_of_stock else rng.randint(3, 120)
        reserved = 0 if out_of_stock else rng.randint(0, min(on_hand - 1, 15))
        nxt = None
        if out_of_stock or on_hand < 20:
            if rng.random() < 0.85:
                nxt = {"date": (DEMO_DATE + timedelta(days=rng.randint(2, 12))).isoformat(),
                       "qty": rng.choice([30, 50, 80, 100])}
                arrivals.append({"date": nxt["date"], "product_code": p["code"], "qty": nxt["qty"], "state": "在途"})
        for _ in range(rng.randint(0, 2)):
            arrivals.append({"date": (DEMO_DATE - timedelta(days=rng.randint(1, 14))).isoformat(),
                             "product_code": p["code"], "qty": rng.choice([20, 40, 60]), "state": "已入库"})
        inv.append({"product_code": p["code"], "on_hand": on_hand, "reserved": reserved,
                    "next_arrival_date": nxt["date"] if nxt else None,
                    "next_arrival_qty": nxt["qty"] if nxt else None})
    arrivals.sort(key=lambda a: a["date"], reverse=True)
    return inv, arrivals


# ----------------------------------------------------------- script library ---
HELLO = "안녕하세요, 고객님. 문의 주셔서 감사합니다.\n"
SORRY = "안녕하세요, 고객님. 불편을 드려 죄송합니다.\n"

SCRIPTS = [
    dict(category="shipping_status", category_zh="配送进度", title="配送进度查询", requires=["order"],
         examples=["주문한 상품이 언제 도착하나요?", "배송이 어디까지 왔는지 확인해 주세요.",
                   "배송 조회를 해도 정보가 나오지 않아요.", "아직 상품을 못 받았는데 언제 오나요?"],
         keywords=["배송", "도착", "택배", "어디"],
         reply_ko=HELLO + "주문번호 {order_no} 상품은 {progress_line}. {eta_line}\n{tracking_line}\n"
                          "조금만 기다려 주시면 안전하게 배송해 드리겠습니다. 감사합니다.",
         reply_zh="您好，感谢咨询。\n订单 {order_no} {progress_line}。{eta_line}\n{tracking_line}\n请您再耐心等待，谢谢。"),
    dict(category="customs", category_zh="清关进度", title="清关进度说明", requires=["order"],
         examples=["통관이 왜 이렇게 오래 걸리나요?", "통관 진행 상황을 알려주세요.",
                   "세관에서 연락이 왔는데 통관이 안 끝났어요."],
         keywords=["통관", "세관"],
         reply_ko=HELLO + "주문번호 {order_no} 상품은 {progress_line}. {customs_line}\n"
                          "통관은 보통 영업일 기준 2~3일 정도 소요되며, 완료되는 대로 국내 택배로 인계됩니다. {eta_line}\n"
                          "조금만 기다려 주시면 감사하겠습니다.",
         reply_zh="您好，感谢咨询。\n订单 {order_no} {progress_line}。{customs_line}\n"
                  "清关一般需要 2 至 3 个工作日，完成后会转交韩国境内快递。{eta_line}\n请您耐心等待，谢谢。"),
    dict(category="stock", category_zh="库存与到货", title="库存与补货时间", requires=["product"],
         examples=["이 상품 재고 있나요?", "품절인데 언제 재입고되나요?", "지금 주문하면 바로 출고되나요?"],
         keywords=["재고", "품절", "재입고", "출고"],
         reply_ko=HELLO + "{product_ref} 상품은 {stock_line}\n추가로 궁금하신 점이 있으시면 언제든지 문의해 주세요. 감사합니다.",
         reply_zh="您好，感谢咨询。\n{product_ref}：{stock_line}\n如有其他问题欢迎随时咨询，谢谢。"),
    dict(category="delivery_time", category_zh="配送时效", title="海外直邮配送时效", requires=[],
         examples=["주문하면 며칠 정도 걸리나요?", "해외배송 기간이 얼마나 되나요?", "언제까지 받을 수 있나요?"],
         keywords=["며칠", "기간", "해외배송"],
         reply_ko=HELLO + "저희 상품은 해외에서 직접 발송되는 상품으로, 결제 후 영업일 기준 7~12일 정도 소요됩니다.\n"
                          "통관 상황에 따라 1~2일 정도 차이가 있을 수 있는 점 양해 부탁드립니다. 감사합니다.",
         reply_zh="您好，感谢咨询。\n本店商品为海外直邮，付款后约 7 至 12 个工作日送达。\n受清关影响可能有 1 至 2 天出入，敬请谅解。谢谢。"),
    dict(category="cancel", category_zh="取消订单", title="取消订单", requires=["order"], manual_only=True,
         examples=["주문을 취소하고 싶어요.", "잘못 주문해서 취소 부탁드립니다.", "출고 전이면 취소해 주세요."],
         keywords=["취소"],
         reply_ko=SORRY + "주문 취소 요청은 담당자가 출고 여부를 확인한 뒤 바로 처리해 드리겠습니다.\n조금만 기다려 주시면 감사하겠습니다.",
         reply_zh="您好，给您带来不便非常抱歉。\n取消订单需由专人确认是否已发货后为您处理，请稍候。",
         note_zh="先看订单状态：未出库可直接取消；已出库走拒收或退货流程。"),
    dict(category="return_refund", category_zh="退货退款", title="退货与退款", requires=["order"], manual_only=True,
         examples=["반품하고 싶습니다.", "환불은 언제 되나요?", "단순 변심인데 반품 가능한가요?"],
         keywords=["반품", "환불"],
         reply_ko=SORRY + "반품 및 환불 문의는 담당자가 주문 내용을 확인한 뒤 순차적으로 안내드리고 있습니다.\n빠르게 확인하여 연락드리겠습니다. 감사합니다.",
         reply_zh="您好，给您带来不便非常抱歉。\n退货退款需由专人核对订单后依次答复，我们会尽快联系您。谢谢。",
         note_zh="核对签收日期和商品状态；无理由退货需买家承担国际退货运费。（演示用的假设政策）"),
    dict(category="exchange", category_zh="换货", title="换货", requires=["order"], manual_only=True,
         examples=["교환하고 싶어요.", "다른 색상으로 교환 가능한가요?", "사이즈 교환은 어떻게 하나요?"],
         keywords=["교환"],
         reply_ko=SORRY + "교환 문의는 담당자가 재고와 주문 내용을 확인한 뒤 안내드리겠습니다.\n조금만 기다려 주시면 감사하겠습니다.",
         reply_zh="您好，给您带来不便非常抱歉。\n换货需由专人确认库存和订单后答复，请稍候。",
         note_zh="先查目标规格库存，再确认往返运费由谁承担。（演示用的假设政策）"),
    dict(category="defect", category_zh="质量问题", title="破损与故障", requires=["order"], manual_only=True,
         examples=["상품이 파손되어 왔어요.", "작동이 안 됩니다. 불량인 것 같아요.", "받아보니 깨져 있어요."],
         keywords=["파손", "불량", "고장", "깨져", "작동"],
         reply_ko=SORRY + "받으신 상품에 문제가 있어 정말 죄송합니다. 담당자가 내용을 확인한 뒤 바로 연락드리겠습니다.\n"
                          "상품 상태를 확인할 수 있는 사진을 보내주시면 더 빠르게 처리해 드릴 수 있습니다.",
         reply_zh="您好，给您带来不便非常抱歉。\n收到的商品有问题，我们深表歉意，专人核实后会马上联系您。\n如能提供商品照片，处理会更快。",
         note_zh="请买家提供照片；登记售后工单，按破损或故障分别处理。"),
    dict(category="wrong_item", category_zh="错发漏发", title="错发与漏发", requires=["order"], manual_only=True,
         examples=["주문한 것과 다른 상품이 왔어요.", "오배송된 것 같습니다.", "수량이 부족하게 왔어요."],
         keywords=["오배송", "다른 상품", "누락", "부족"],
         reply_ko=SORRY + "주문하신 내용과 다르게 배송되어 정말 죄송합니다. 담당자가 출고 기록을 확인한 뒤 바로 연락드리겠습니다.",
         reply_zh="您好，给您带来不便非常抱歉。\n发货与订单不符，我们深表歉意，专人核对出库记录后会马上联系您。",
         note_zh="核对出库记录和发货影像，确认后补发或换货。"),
    dict(category="complaint", category_zh="投诉", title="投诉与不满", requires=[], manual_only=True,
         examples=["몇 번을 문의해도 답이 없어요.", "책임자와 통화하고 싶습니다.", "너무 화가 납니다. 신고하겠습니다."],
         keywords=["신고", "책임자", "화가", "최악"],
         reply_ko=SORRY + "이용에 불편을 드린 점 진심으로 사과드립니다. 담당 책임자가 내용을 확인한 뒤 직접 연락드리겠습니다.",
         reply_zh="您好，给您带来不便非常抱歉。\n对此次不愉快的体验我们诚恳致歉，负责人核实后会直接联系您。",
         note_zh="升级给客服主管，当天回复。"),
    dict(category="address_change", category_zh="修改收货信息", title="修改地址或联系方式", requires=["order"], manual_only=True,
         examples=["배송지 주소를 변경하고 싶어요.", "받는 사람 연락처를 바꿀 수 있나요?", "이사를 해서 주소를 바꿔야 해요."],
         keywords=["주소", "배송지", "연락처"],
         reply_ko=SORRY + "배송지 정보 변경은 담당자가 출고 여부를 확인한 뒤 처리해 드리겠습니다.\n조금만 기다려 주시면 감사하겠습니다.",
         reply_zh="您好，给您带来不便非常抱歉。\n修改收货信息需由专人确认是否已发货后处理，请稍候。",
         note_zh="未出库可改；已进入国际运输段一般无法修改。"),
    dict(category="customs_code_change", category_zh="修改通关号", title="修改个人通关号", requires=["order"], manual_only=True,
         examples=["개인통관고유부호를 잘못 입력했어요.", "통관부호를 수정하고 싶습니다.", "통관부호를 변경할 수 있나요?"],
         keywords=["통관부호", "개인통관고유부호", "잘못 입력", "수정"],
         reply_ko=SORRY + "개인통관고유부호 수정은 담당자가 통관 진행 상태를 확인한 뒤 처리해 드리겠습니다.\n"
                          "정확한 통관부호와 수령인 성함을 함께 알려주시면 더 빠르게 처리됩니다.",
         reply_zh="您好，给您带来不便非常抱歉。\n修改个人通关号需由专人确认清关状态后处理。\n请同时提供正确的通关号和收件人姓名。",
         note_zh="通关号须与收件人实名一致；已申报的需联系物流改单。"),
    dict(category="delivered_not_received", category_zh="显示签收未收到", title="显示签收但未收到", requires=["order"], manual_only=True,
         examples=["배송완료인데 상품을 받지 못했어요.", "배송완료로 뜨는데 물건이 없어요."],
         keywords=["배송완료", "못 받", "받지 못"],
         reply_ko=SORRY + "배송완료로 확인되지만 상품을 받지 못하셨다니 정말 죄송합니다. 담당자가 택배사에 바로 확인한 뒤 연락드리겠습니다.",
         reply_zh="您好，给您带来不便非常抱歉。\n系统显示已签收但您未收到，专人会立即向快递公司核实后联系您。",
         note_zh="向承运商查签收凭证，24 小时内回复买家。"),
    dict(category="receipt", category_zh="发票与收据", title="现金收据与购买凭证", requires=[],
         examples=["현금영수증 발급 가능한가요?", "영수증을 받을 수 있나요?", "세금계산서 발행되나요?"],
         keywords=["영수증", "세금계산서"],
         reply_ko=HELLO + "구매 영수증은 구매하신 쇼핑몰의 주문 내역에서 직접 출력하실 수 있습니다.\n"
                          "현금영수증은 결제 시 선택하신 방식에 따라 쇼핑몰에서 자동 발급됩니다. 감사합니다.",
         reply_zh="您好，感谢咨询。\n购买凭证可在平台订单详情中自行打印。\n现金收据按付款时选择的方式由平台自动开具。谢谢。"),
    dict(category="usage", category_zh="使用说明", title="使用方法与电压", requires=[],
         examples=["사용 설명서가 들어 있나요?", "한국 전압에서 사용할 수 있나요?", "처음에 충전은 얼마나 해야 하나요?"],
         keywords=["설명서", "사용", "220V", "충전"],
         reply_ko=HELLO + "{product_ref} 상품의 사용 방법은 상세페이지 하단의 사용 안내에서 확인하실 수 있습니다.\n"
                          "전원이 필요한 상품은 모두 한국 220V 환경에서 사용 가능한 사양으로 발송됩니다. 감사합니다.",
         reply_zh="您好，感谢咨询。\n{product_ref}的使用方法见详情页下方的使用说明。\n需要用电的商品均按韩国 220V 规格发货。谢谢。"),
    dict(category="size", category_zh="尺码咨询", title="尺码选择", requires=[],
         examples=["어떤 사이즈로 주문해야 하나요?", "실측 사이즈를 알려주세요.", "평소 입는 사이즈로 주문하면 되나요?"],
         keywords=["사이즈", "실측", "키"],
         reply_ko=HELLO + "{product_ref} 상품은 정사이즈로 제작되었으며, 상세페이지의 사이즈표에서 실측 치수를 확인하실 수 있습니다.\n"
                          "넉넉한 핏을 원하시면 한 사이즈 크게 주문하시는 것을 추천드립니다. 감사합니다.",
         reply_zh="您好，感谢咨询。\n{product_ref}为标准尺码，实测尺寸见详情页尺码表。\n喜欢宽松的话建议选大一码。谢谢。"),
    dict(category="combined_shipping", category_zh="合并发货", title="合并发货与运费", requires=[],
         examples=["합배송 되나요?", "묶음배송으로 받을 수 있나요?", "배송비는 한 번만 내면 되나요?"],
         keywords=["합배송", "묶음배송", "배송비"],
         reply_ko=HELLO + "같은 날 함께 주문하신 상품은 한 번에 묶어서 발송해 드리며 배송비는 한 번만 부과됩니다.\n"
                          "따로 주문하신 경우에는 출고 전에 말씀해 주시면 합배송 가능 여부를 확인해 드리겠습니다. 감사합니다.",
         reply_zh="您好，感谢咨询。\n同一天一起下单的商品会合并发货，运费只收一次。\n分开下单的请在发货前告知，我们确认能否合并。谢谢。"),
    dict(category="coupon", category_zh="优惠活动", title="优惠券与活动", requires=[],
         examples=["쿠폰 적용이 안 돼요.", "할인 행사는 언제 하나요?", "할인 쿠폰은 어디서 받나요?"],
         keywords=["쿠폰", "할인"],
         reply_ko=HELLO + "쿠폰은 쇼핑몰의 쿠폰함에서 내려받은 뒤 결제 단계에서 선택하시면 적용됩니다.\n"
                          "진행 중인 할인 행사는 스토어 메인 화면의 공지에서 확인하실 수 있습니다. 감사합니다.",
         reply_zh="您好，感谢咨询。\n优惠券需先在平台领券中心领取，结算时选择即可使用。\n进行中的活动见店铺首页公告。谢谢。"),
    dict(category="thanks", category_zh="感谢与好评", title="感谢回复", requires=[],
         examples=["잘 받았습니다. 감사합니다.", "상품이 마음에 들어요.", "빠른 배송 감사합니다."],
         keywords=["감사", "잘 받았"],
         reply_ko="안녕하세요, 고객님. 소중한 말씀 감사합니다.\n앞으로도 좋은 상품과 서비스로 보답하겠습니다. 좋은 하루 보내세요.",
         reply_zh="您好，感谢您的留言。\n我们会继续提供好的商品和服务，祝您生活愉快。"),
]

RULES = [
    dict(id="R1", name="退货退款", type="keyword", any=["반품", "환불"]),
    dict(id="R2", name="换货", type="keyword", any=["교환"]),
    dict(id="R3", name="取消或改单", type="keyword",
         any=["취소", "주소 변경", "주소를 변경", "배송지", "연락처를 바꿀", "잘못 입력", "수정 부탁", "변경할 수", "변경 부탁"]),
    dict(id="R4", name="质量问题或错发", type="keyword",
         any=["파손", "불량", "고장", "깨져", "작동이 안", "오배송", "다른 상품이", "다른 게 왔", "부족하게", "누락"]),
    dict(id="R5", name="投诉或情绪激动", type="keyword",
         any=["신고", "소비자원", "책임자", "화가", "최악", "사기", "답이 없"]),
    dict(id="R6", name="显示签收但未收到", type="keyword", all=["배송완료"],
         any=["못 받", "받지 못", "안 왔", "없습니다", "없어요"]),
    dict(id="R7", name="查不到订单", type="order_not_found"),
    dict(id="R8", name="超期未到货", type="overdue", days=3),
    dict(id="R9", name="话术匹配度低", type="low_confidence", threshold=0.15),
    dict(id="R10", name="人工处理类话术", type="manual_script"),
]

# ------------------------------------------------------------------ inquiries ---
# (korean, chinese, how the order / product is known): "text" = written in the
# message, "attached" = linked by the shop back office, "none" = unknown.
HANDOFF_CATEGORIES = {s["category"] for s in SCRIPTS if s.get("manual_only")}

ORDER_FILTER = {
    "shipping_status": ("상품준비중", "해외배송중", "국내배송중"),
    "customs": ("통관중",),
    "cancel": ("결제완료", "상품준비중"),
    "address_change": ("결제완료", "상품준비중", "해외배송중"),
    "customs_code_change": ("상품준비중", "해외배송중", "통관중"),
    "return_refund": ("배송완료",),
    "exchange": ("배송완료",),
    "defect": ("배송완료",),
    "wrong_item": ("배송완료",),
    "delivered_not_received": ("배송완료",),
    "complaint": ("해외배송중", "통관중", "국내배송중", "배송완료"),
}

PHRASES = {
    "shipping_status": [
        ("주문번호 {order_no}인데요, 지금 어디쯤 왔는지 알 수 있을까요?", "订单号 {order_no}，想知道现在到哪里了？", "text"),
        ("주문한 지 일주일이 됐는데 아직 안 와요. 언제쯤 받을 수 있나요?", "下单一周了还没到，大概什么时候能收到？", "attached"),
        ("배송 조회를 해도 아무 정보가 안 떠요. 확인 부탁드려요. {order_no}", "查物流没有任何信息，麻烦确认一下。{order_no}", "text"),
        ("택배 언제 도착해요?", "快递什么时候到？", "none"),
        ("{order_no} 주문 건 출고는 됐나요? 도착 예정일이 궁금합니다.", "{order_no} 这单发货了吗？想知道预计到货日。", "text"),
    ],
    "customs": [
        ("통관 중이라고만 뜨고 며칠째 그대로예요. 왜 이렇게 오래 걸리죠? {order_no}", "一直显示清关中，好几天没变化，为什么这么久？{order_no}", "text"),
        ("세관에서 문자가 왔는데 통관 진행 상황 좀 알려주세요. 주문번호 {order_no}", "收到海关短信，请告知清关进度。订单号 {order_no}", "text"),
        ("통관이 아직도 안 끝났나요? 언제 넘어오는지 궁금해요.", "清关还没结束吗？想知道什么时候放行。", "attached"),
    ],
    "stock": [
        ("{product_name} 지금 재고 있나요?", "{product_name_zh}现在有货吗？", "text"),
        ("상품코드 {product_code} 품절이던데 언제 재입고되나요?", "商品编码 {product_code} 显示缺货，什么时候补货？", "text"),
        ("{product_name} 오늘 주문하면 바로 출고되나요? 재고 확인 부탁드립니다.", "{product_name_zh}今天下单能马上发货吗？请确认库存。", "text"),
        ("이 상품 재입고 예정이 있나요?", "这个商品有补货计划吗？", "attached"),
    ],
    "delivery_time": [
        ("주문하면 보통 며칠 정도 걸리나요?", "下单后一般要几天？", "none"),
        ("해외배송 상품이라는데 배송 기간이 어떻게 되나요?", "说是海外直邮，配送周期多久？", "none"),
        ("지금 결제하면 다음 주 안에 받을 수 있을까요?", "现在付款下周内能收到吗？", "none"),
    ],
    "cancel": [
        ("주문 취소하고 싶어요. {order_no}", "想取消订单。{order_no}", "text"),
        ("잘못 주문했어요. 취소 처리 부탁드립니다.", "下错单了，麻烦取消。", "attached"),
        ("아직 출고 전이면 주문 취소해 주세요. 주문번호 {order_no}", "还没发货的话请取消订单。订单号 {order_no}", "text"),
    ],
    "return_refund": [
        ("상품이 마음에 안 들어서 반품하고 싶습니다. {order_no}", "不喜欢这个商品，想退货。{order_no}", "text"),
        ("환불은 언제 되나요? 반품 접수한 지 꽤 됐는데요.", "退款什么时候到？退货申请已经很久了。", "attached"),
        ("단순 변심인데 반품 가능한가요? 반품 배송비는 얼마인가요?", "只是不想要了，可以退货吗？退货运费多少？", "attached"),
    ],
    "exchange": [
        ("사이즈가 안 맞아서 교환하고 싶어요. {order_no}", "尺码不合适，想换货。{order_no}", "text"),
        ("다른 색상으로 교환 가능한가요?", "可以换成别的颜色吗？", "attached"),
        ("교환 신청은 어떻게 하나요? 주문번호 {order_no}", "怎么申请换货？订单号 {order_no}", "text"),
    ],
    "defect": [
        ("받아보니 상품이 파손되어 있어요. 사진 첨부합니다. {order_no}", "收到发现商品破损，附上照片。{order_no}", "text"),
        ("충전을 해도 작동이 안 됩니다. 불량인 것 같아요.", "充了电也不工作，应该是次品。", "attached"),
        ("박스를 열어보니 깨져 있네요. 어떻게 해야 하나요? {order_no}", "打开箱子发现碎了，该怎么办？{order_no}", "text"),
    ],
    "wrong_item": [
        ("주문한 것과 다른 상품이 왔어요. {order_no}", "收到的和订的不是同一个商品。{order_no}", "text"),
        ("색상이 다른 게 왔는데 오배송인 것 같습니다.", "颜色发错了，应该是错发。", "attached"),
        ("수량이 부족하게 왔어요. 2개 주문했는데 1개만 왔습니다. {order_no}", "数量少了，订了 2 个只到 1 个。{order_no}", "text"),
    ],
    "complaint": [
        ("몇 번을 문의해도 답이 없네요. 정말 화가 납니다. 책임자 연결해 주세요.", "问了好几次都没人回，真的很生气，请转负责人。", "attached"),
        ("이런 식이면 소비자원에 신고하겠습니다.", "再这样我就向消费者院投诉。", "attached"),
        ("최악이네요. 다시는 여기서 안 삽니다. {order_no}", "太差了，再也不在这买了。{order_no}", "text"),
    ],
    "address_change": [
        ("배송지 주소를 변경하고 싶어요. {order_no}", "想修改收货地址。{order_no}", "text"),
        ("이사를 해서 주소 변경 부탁드립니다. 아직 출고 전이죠?", "搬家了，麻烦改一下地址，还没发货吧？", "attached"),
        ("받는 사람 연락처를 바꿀 수 있을까요? 주문번호 {order_no}", "能改收件人电话吗？订单号 {order_no}", "text"),
    ],
    "customs_code_change": [
        ("개인통관고유부호를 잘못 입력했어요. 수정 부탁드립니다. {order_no}", "个人通关号填错了，请帮忙修改。{order_no}", "text"),
        ("통관부호를 다른 사람 걸로 변경할 수 있나요?", "通关号能换成别人的吗？", "attached"),
    ],
    "delivered_not_received": [
        ("배송완료라고 나오는데 상품을 못 받았어요. {order_no}", "显示已签收，但我没收到。{order_no}", "text"),
        ("택배 기사님이 문 앞에 뒀다는데 아무것도 없습니다. 배송완료로 뜨는데요.", "快递员说放门口了，但什么都没有，系统显示已签收。", "attached"),
        ("배송완료 문자를 받았는데 물건이 안 왔어요. 확인해 주세요. {order_no}", "收到签收短信但东西没到，请确认。{order_no}", "text"),
    ],
    "receipt": [
        ("현금영수증 발급 가능한가요?", "可以开现金收据吗？", "none"),
        ("세금계산서나 영수증을 받을 수 있을까요? 회사 비용 처리용입니다.", "能开税务发票或收据吗？公司报销用。", "none"),
        ("구매 영수증은 어디서 출력하나요?", "购买凭证在哪里打印？", "none"),
    ],
    "usage": [
        ("사용 설명서가 한국어로 들어 있나요?", "里面有韩语说明书吗？", "none"),
        ("이 제품 한국 220V에서 그대로 사용할 수 있나요?", "这个产品在韩国 220V 下能直接用吗？", "attached_product"),
        ("처음 사용할 때 충전은 얼마나 해야 하나요?", "第一次使用要充多久电？", "attached_product"),
    ],
    "size": [
        ("평소 M 사이즈 입는데 어떤 사이즈로 주문해야 할까요?", "平时穿 M 码，应该订哪个码？", "attached_product"),
        ("{product_name} 실측 사이즈 좀 알려주세요.", "请告知{product_name_zh}的实测尺寸。", "text"),
        ("키 175에 70kg인데 L 사이즈 맞을까요?", "身高 175、体重 70kg，L 码合适吗？", "none"),
    ],
    "combined_shipping": [
        ("두 가지 상품을 같이 주문하면 합배송 되나요?", "两种商品一起下单能合并发货吗？", "none"),
        ("따로 주문한 두 건을 묶음배송으로 받을 수 있을까요?", "分开下的两单能合并配送吗？", "none"),
        ("여러 개 주문 시 배송비는 한 번만 내면 되나요?", "买多件运费只付一次吗？", "none"),
    ],
    "coupon": [
        ("쿠폰 적용이 안 되는데 확인 부탁드려요.", "优惠券用不了，麻烦确认。", "none"),
        ("다음 할인 행사는 언제 하나요?", "下次打折活动是什么时候？", "none"),
        ("첫 구매 할인 쿠폰은 어디서 받나요?", "首单优惠券在哪里领？", "none"),
    ],
    "thanks": [
        ("잘 받았습니다. 감사합니다!", "已收到，谢谢！", "none"),
        ("빠른 답변 감사해요. 잘 쓸게요.", "谢谢快速回复，我会好好用的。", "none"),
    ],
}

FASHION_ONLY = {"size"}


def make_inquiries(products, orders):
    rows, labels = [], []

    def pick_order(category, delayed=False):
        allowed = ORDER_FILTER.get(category)
        pool = [o for o in orders if o["delayed"] == delayed and (allowed is None or o["status"] in allowed)]
        return rng.choice(pool)

    def add(category, ko, zh, mode, order=None, handoff=None):
        product = None
        if mode in ("text", "attached") and category in ORDER_FILTER:
            order = order or pick_order(category)
        if category in ("stock", "usage", "size"):
            pool = [p for p in products if p["category"] == "FS"] if category in FASHION_ONLY else products
            product = rng.choice(pool)
        fmt = {"order_no": order["order_no"] if order else "",
               "product_name": product["name_ko"] if product else "",
               "product_name_zh": product["name_zh"] if product else "",
               "product_code": product["code"] if product else ""}
        qid = f"Q{len(rows) + 1:04d}"
        rows.append({
            "id": qid,
            "channel": order["channel"] if order else rng.choice(CHANNELS),
            "buyer": order["buyer"] if order else masked_name(),
            "text_ko": ko.format(**fmt),
            "text_zh": zh.format(**fmt),
            "order_no": order["order_no"] if order and mode in ("text", "attached") else None,
            "product_code": product["code"] if product and mode in ("attached", "attached_product") else None,
        })
        if handoff is None:
            handoff = category in HANDOFF_CATEGORIES
        labels.append({"id": qid, "category": category, "handoff": handoff})

    for category, phrases in PHRASES.items():
        for ko, zh, mode in phrases:
            add(category, ko, zh, mode)

    # Orders that are past their expected arrival date: the reply itself is a
    # normal shipping answer, but a person has to chase the carrier.
    for ko, zh, mode in PHRASES["shipping_status"][:3]:
        add("shipping_status", ko, zh, mode, order=pick_order(None, delayed=True), handoff=True)

    # An order number that does not exist.
    rows_before = len(rows)
    add("shipping_status", "주문번호 20261101-00000 배송 상태 확인 부탁드립니다.",
        "请确认订单 20261101-00000 的配送状态。", "none", handoff=True)
    assert len(rows) == rows_before + 1

    # Shuffle arrival order and stamp times within the demo day.
    order_idx = list(range(len(rows)))
    rng.shuffle(order_idx)
    start = datetime(DEMO_DATE.year, DEMO_DATE.month, DEMO_DATE.day, 9, 0)
    for n, i in enumerate(order_idx):
        rows[i]["created_at"] = (start + timedelta(minutes=7 * n + rng.randint(0, 5))).isoformat(timespec="minutes")
    return rows, labels


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def main():
    OUT.mkdir(exist_ok=True)
    products = make_products()
    orders = make_orders(products)
    inventory, arrivals = make_inventory(products)
    inquiries, labels = make_inquiries(products, orders)
    delayed = sum(o.pop("delayed") for o in orders)  # generator-only flag, not part of the data
    scripts = [{"id": f"S{i + 1:02d}", "manual_only": False, "note_zh": "", "enabled": True, **s}
               for i, s in enumerate(SCRIPTS)]
    rules = [{"enabled": True, **r} for r in RULES]

    dump("meta.json", {"demo_date": DEMO_DATE.isoformat(), "seed": SEED,
                       "note": "All data in this folder is synthetic (scripts/make_demo_data.py)."})
    dump("products.json", products)
    dump("orders.json", orders)
    dump("inventory.json", inventory)
    dump("arrivals.json", arrivals)
    dump("inquiries.json", inquiries)
    dump("eval_labels.json", labels)
    dump("scripts.json", scripts)
    dump("rules.json", rules)
    print(f"products {len(products)}  orders {len(orders)}  inquiries {len(inquiries)}  "
          f"scripts {len(scripts)}  rules {len(rules)}  delayed {delayed}")


if __name__ == "__main__":
    main()

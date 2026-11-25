# -*- coding: utf-8 -*-
"""Shared constants: order statuses and identifier formats used by the demo data."""
import re

# Order life cycle of a cross-border parcel, in order.
STATUSES = ["결제완료", "상품준비중", "해외배송중", "통관중", "국내배송중", "배송완료"]

STATUS_ZH = {
    "결제완료": "已付款",
    "상품준비중": "备货中",
    "해외배송중": "国际运输中",
    "통관중": "清关中",
    "국내배송중": "韩国境内派送中",
    "배송완료": "已签收",
}

# Identifier formats (all synthetic).
ORDER_NO_RE = re.compile(r"(?<!\d)20\d{6}-\d{5}(?!\d)")
PRODUCT_CODE_RE = re.compile(r"(?<![A-Za-z])[A-Z]{2}-\d{5}(?!\d)")
CUSTOMS_NO_RE = re.compile(r"(?<![A-Za-z0-9])P\d{12}(?!\d)")

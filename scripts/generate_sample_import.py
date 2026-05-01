# -*- coding: utf-8 -*-
"""Generate a small sample import Excel for the marketplace_import wizard.

Outputs scripts/sample_shopee_import.xlsx with 5 orders × multi-line items.
"""
from openpyxl import Workbook
from datetime import datetime, timedelta

ORDERS = [
    # (order_sn, shop, sku, qty, brand, fake)
    ("260331JQ2E3CEE", "DaengGiMeoRi", "DUT300",  1, "DAENG-GI-MEO-RI", "N"),
    ("260331JNYFCNFC", "KissMyBody",   "KHKB038", 1, "KISS-MY-BODY",    "N"),
    ("260331JNYFCNFC", "KissMyBody",   "KTSD088", 1, "KISS-MY-BODY",    "N"),
    ("260331JSMTYW1R", "KissMyBody",   "KMI088",  2, "KISS-MY-BODY",    "N"),
    ("260331JSMTYW1R", "KissMyBody",   "KSF180",  2, "KISS-MY-BODY",    "N"),
    ("260331JRE716B3", "KissMyBody",   "KTMH088", 1, "KISS-MY-BODY",    "N"),
    ("260331JRE716B3", "KissMyBody",   "KTMM088", 1, "KISS-MY-BODY",    "N"),
    ("260331JRE716B3", "KissMyBody",   "KTSD088", 1, "KISS-MY-BODY",    "N"),
    ("260331JT5H277A", "Skinoxy",      "OXY100",  1, "SKINOXY",         "N"),
    ("260331JT5H277A", "Skinoxy",      "OXYBB30", 1, "SKINOXY",         "N"),
    ("260331JFAKE001", "KissOfBeauty", "KOB101",  3, "KISS-OF-BEAUTY",  "Y"),
    ("260331JFAKE001", "KissOfBeauty", "KOB606",  5, "KISS-OF-BEAUTY",  "Y"),
]

wb = Workbook()
ws = wb.active
ws.title = "Shopee"
ws.append(["order_sn", "shop", "order_date", "sku", "qty", "brand", "fake"])

base = datetime(2026, 3, 31, 8, 0, 0)
for i, (order_sn, shop, sku, qty, brand, fake) in enumerate(ORDERS):
    # Stagger order_date by 5 minutes per row of the same order_sn.
    offset = i * 5
    ws.append([
        order_sn, shop,
        (base + timedelta(minutes=offset)).strftime("%Y-%m-%d %H:%M:%S"),
        sku, qty, brand, fake,
    ])

out = "scripts/sample_shopee_import.xlsx"
wb.save(out)
print(f"Wrote {out}: {len(ORDERS)} rows across "
      f"{len(set(o[0] for o in ORDERS))} unique orders")

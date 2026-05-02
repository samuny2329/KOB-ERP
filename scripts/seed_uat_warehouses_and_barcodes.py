# -*- coding: utf-8 -*-
"""Materialise the 31 UAT warehouses local doesn't have yet, then
patch real EAN-13 barcodes onto products from UAT data.

Run via Odoo shell:
    docker exec -i kob-odoo-19 odoo shell -d kobdb --no-http \
        --stop-after-init < scripts/seed_uat_warehouses_and_barcodes.py

Pre-reqs (copy data files into the container):
    docker cp scripts/uat_data/kob_uat_warehouses.json kob-odoo-19:/tmp/
    docker cp scripts/uat_data/kob_uat_barcodes.json   kob-odoo-19:/tmp/

Notes
-----
* UAT companies are id 1/2/3 (KOB / BTV / CMN).  Local CMN sits at
  id=4 — we map UAT company 3 → local company 4 here.
"""

import json
import logging
from pathlib import Path

_logger = logging.getLogger("kob_seed_wh_bc")

UAT_CO_TO_LOCAL = {1: 1, 2: 2, 3: 4}  # CMN local id is 4


def _load(path):
    if not Path(path).exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


whs_data = _load("/tmp/kob_uat_warehouses.json")
bc_data = _load("/tmp/kob_uat_barcodes.json")
print(f"[seed] warehouses={len(whs_data) if whs_data else 'MISSING'} "
      f"barcodes={len(bc_data) if bc_data else 'MISSING'}")

# ── 1. Warehouses ─────────────────────────────────────────────────
WH = env["stock.warehouse"]
existing_codes = {w.code for w in WH.search([])}
print(f"[seed] local already has codes: {sorted(existing_codes)}")

created_wh = 0
skipped_wh = 0
for w in (whs_data or []):
    code = w["code"]
    if code in existing_codes:
        skipped_wh += 1
        continue
    co_id = UAT_CO_TO_LOCAL.get(w["co"])
    if not co_id:
        skipped_wh += 1
        continue
    try:
        WH.sudo().create({
            "name":            w["name"],
            "code":            code,
            "company_id":      co_id,
            "reception_steps": w.get("recv", "one_step"),
            "delivery_steps":  w.get("dlv", "ship_only"),
        })
        created_wh += 1
    except Exception as e:
        print(f"[seed] FAIL create warehouse {code}: {e}")

env.cr.commit()
print(f"[seed] warehouses — created={created_wh} skipped={skipped_wh}")

# ── 2. Real EAN-13 barcodes ──────────────────────────────────────
Prod = env["product.product"]
patched = 0
unchanged = 0
not_found = 0
clashes = 0

local_by_sku = {}
for p in Prod.search([("default_code", "!=", False)]):
    local_by_sku.setdefault(p.default_code, []).append(p)

for entry in (bc_data or []):
    sku = entry.get("sku")
    bc = entry.get("bc")
    if not sku or not bc:
        continue
    matches = local_by_sku.get(sku, [])
    if not matches:
        not_found += 1
        continue
    for prod in matches:
        if prod.barcode == bc:
            unchanged += 1
            continue
        try:
            prod.barcode = bc
            patched += 1
        except Exception as e:
            clashes += 1

env.cr.commit()
print(f"[seed] barcodes — patched={patched} unchanged={unchanged} "
      f"not_found_local={not_found} clashes={clashes}")
print(f"[seed] total warehouses now: {WH.search_count([])}")

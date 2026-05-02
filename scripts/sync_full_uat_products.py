# -*- coding: utf-8 -*-
"""Sync ALL 3,518 UAT products into local kobdb.

Source: scripts/uat_data/kob_uat_full_products.json (captured via the
Chrome extension RPC dump on kissgroupdatacenter.com).

For each SKU:
  * If exists in local — update name + categ_id (mapped) + price
  * If missing — create as consumable, lot-tracked.

UAT companies = 1 KOB / 2 BTV / 3 CMN.  Local CMN sits at id=4 — we
remap.  Products are kept GLOBAL (company_id=NULL) per current local
policy so all 3 companies share the catalogue.
"""

import json
from pathlib import Path

UAT_CO_TO_LOCAL = {1: 1, 2: 2, 3: 4}

p = Path("/tmp/kob_uat_full_products.json")
if not p.exists():
    raise FileNotFoundError("Run docker cp first")

raw = p.read_bytes()
# Strip BOM if present
if raw[:3] == b"\xef\xbb\xbf":
    raw = raw[3:]
data = json.loads(raw.decode("utf-8"))
print(f"[full] loaded {len(data)} entries from UAT")

PT = env["product.template"]
PP = env["product.product"]
PC = env["product.category"]

# Cache — local existing products by SKU
local_by_sku = {}
for pp in PP.search([("default_code", "!=", False)]):
    local_by_sku[pp.default_code] = pp

# Cache categories — match by complete_name segments
def _resolve_cat(name):
    if not name:
        return None
    parts = [s.strip() for s in name.split("/") if s.strip()]
    parent = None
    cat = None
    for seg in parts:
        cat = PC.search([("name", "=", seg)] +
                        ([("parent_id", "=", parent.id)] if parent else
                         [("parent_id", "=", False)]),
                        limit=1)
        if not cat:
            cat = PC.create({
                "name":      seg,
                "parent_id": parent.id if parent else False,
            })
        parent = cat
    return cat

updated = 0
created = 0
skipped = 0

for entry in data:
    sku = entry.get("sku")
    name = (entry.get("name") or "").strip()
    co_id = UAT_CO_TO_LOCAL.get(entry.get("co_id"))
    cat_name = entry.get("cat")
    if not sku or not name:
        skipped += 1
        continue

    target_cat = _resolve_cat(cat_name) if cat_name else None

    pp = local_by_sku.get(sku)
    if pp:
        # Update existing
        vals = {"name": name}
        if target_cat and pp.product_tmpl_id.categ_id != target_cat:
            vals["categ_id"] = target_cat.id
        pp.product_tmpl_id.write(vals)
        updated += 1
        continue

    # Create missing — keep global (company_id null)
    new_vals = {
        "name":         name,
        "default_code": sku,
        "type":         "consu",
        "tracking":     "lot",
        "sale_ok":      True,
        "purchase_ok":  True,
    }
    if target_cat:
        new_vals["categ_id"] = target_cat.id
    if "is_storable" in PT._fields:
        new_vals["is_storable"] = True
    bc = entry.get("bc") or False
    if bc:
        new_vals["barcode"] = bc
    try:
        PT.sudo().create(new_vals)
        created += 1
    except Exception as e:
        print(f"[full] FAIL {sku}: {e}")
        skipped += 1

env.cr.commit()
print(f"[full] DONE — updated={updated} created={created} skipped={skipped}")
print(f"[full] product.template total now: {PT.search_count([])}")

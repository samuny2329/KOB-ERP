"""Import real subcontract BOMs from UAT into kobdb.

Reads /tmp/uat_subcontract_boms.json (copied via docker cp from
scripts/data/uat_subcontract_boms.json) and recreates each BOM on kobdb:

- Match product template by default_code or name (exact then fuzzy-strip suffix)
- Match components by default_code
- Map subcontractor partner: UAT id 12130 (CMN) → kobdb id 75 (CMN)
- Update component costs to UAT real values
- Skip BOMs whose product or any component is missing on kobdb
- Skip if a subcontract BOM already exists for that kobdb template (deduplicate)

Run via:
    docker cp scripts/data/uat_subcontract_boms.json \\
        kob-odoo-19:/tmp/uat_subcontract_boms.json
    MSYS_NO_PATHCONV=1 docker exec -i kob-odoo-19 \\
        env DRY_RUN=0 odoo shell -c /etc/odoo/odoo.conf -d kobdb --no-http \\
        < scripts/import_uat_subcontract_boms.py

Default: DRY_RUN=1 — only prints, no writes.
"""

import json
import os
import re

DRY_RUN = os.environ.get("DRY_RUN", "1") != "0"
print(f"=== {'EXECUTE' if not DRY_RUN else 'DRY RUN'} ===\n")

# UAT partner_id → kobdb partner_id mapping
# CMN: UAT 12130 → kobdb 75
PARTNER_MAP = {12130: 75}

with open("/tmp/uat_subcontract_boms.json") as f:
    boms = json.load(f)
print(f"Loaded {len(boms)} BOMs from UAT JSON\n")

BOM = env["mrp.bom"]
P = env["product.product"]
T = env["product.template"]


def find_template(code, name):
    """Find product.template in kobdb by code, then exact name, then fuzzy name."""
    # 1) by product default_code
    if code:
        v = P.search([("default_code", "=", code)], limit=1)
        if v:
            return v.product_tmpl_id
    # 2) exact name
    t = T.search([("name", "=", name)], limit=1)
    if t:
        return t
    # 3) strip trailing market/variant suffix: [SA] [INTER] [VN] [Rework] (clearance …) etc.
    clean = re.sub(r'\s*[\[\(][^\]\)]*[\]\)]\s*$', '', name).strip()
    if clean != name:
        t = T.search([("name", "=", clean)], limit=1)
        if t:
            return t
        # partial ilike as last resort
        t = T.search([("name", "ilike", clean)], limit=1)
        if t:
            return t
    return None


stats = {
    "created": 0,
    "skipped_existing": 0,
    "missing_product": 0,
    "missing_components": 0,
    "no_partner_map": 0,
    "duplicate_in_uat": 0,
}
missing_products = []
seen_tmpl_ids = set()

for ub in boms:
    # 1) Map subcontractor_ids early — skip unmapped partners
    mapped_subs = [PARTNER_MAP[sid] for sid in ub["sub_ids"] if sid in PARTNER_MAP]
    if not mapped_subs:
        stats["no_partner_map"] += 1
        continue

    # 2) Find product template on kobdb
    tmpl = find_template(ub["tmpl_code"], ub["tmpl_name"])
    if not tmpl:
        stats["missing_product"] += 1
        missing_products.append(f"[{ub['tmpl_code']}] {ub['tmpl_name']}")
        continue

    # 3) Deduplicate UAT — multiple UAT BOMs for same kobdb template → take first
    if tmpl.id in seen_tmpl_ids:
        stats["duplicate_in_uat"] += 1
        continue
    seen_tmpl_ids.add(tmpl.id)

    # 4) Skip if subcontract BOM already exists for this product
    existing = BOM.search([
        ("product_tmpl_id", "=", tmpl.id),
        ("type", "=", "subcontract"),
    ], limit=1)
    if existing:
        stats["skipped_existing"] += 1
        continue

    # 5) Resolve components
    bom_lines = []
    missing = False
    for c in ub["components"]:
        comp = P.search([("default_code", "=", c["code"])], limit=1)
        if not comp:
            missing = True
            if DRY_RUN:
                print(f"  MISSING COMP {c['code']} for {ub['tmpl_name']}")
            break
        bom_lines.append((0, 0, {
            "product_id": comp.id,
            "product_qty": c["qty"],
        }))
        if c.get("cost") and not DRY_RUN:
            if abs(comp.standard_price - c["cost"]) > 0.01:
                comp.write({"standard_price": c["cost"]})
    if missing:
        stats["missing_components"] += 1
        continue

    # 6) Create BOM
    if not DRY_RUN:
        BOM.create({
            "product_tmpl_id": tmpl.id,
            "code": ub["code"],
            "type": "subcontract",
            "subcontractor_ids": [(6, 0, mapped_subs)],
            "product_qty": ub["qty"],
            "bom_line_ids": bom_lines,
        })
        print(f"  Created BOM: [{ub['tmpl_code']}] {ub['tmpl_name'][:60]}")
    stats["created"] += 1

if not DRY_RUN:
    env.cr.commit()

print(f"\nStats: {stats}")
print(f"  Total accounted: {sum(stats.values())}")
if missing_products:
    print(f"\nMissing FG products ({len(missing_products)}):")
    for m in missing_products:
        print(f"  {m}")

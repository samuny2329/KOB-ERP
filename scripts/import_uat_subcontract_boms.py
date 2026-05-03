"""Import real subcontract BOMs from UAT into kobdb.

Reads /tmp/uat_subcontract_boms.json (copied via docker cp from
scripts/data/uat_subcontract_boms.json) and recreates each BOM on kobdb:

- Match product template by default_code or name
- Match components by default_code
- Map subcontractor partner: UAT id 12130 (CMN) → kobdb id 75 (CMN)
- Update component costs to UAT real values
- Skip BOMs whose product or any component is missing on kobdb

Run via:
    docker cp scripts/data/uat_subcontract_boms.json \\
        kob-odoo-19:/tmp/uat_subcontract_boms.json
    docker exec -i -e DRY_RUN=0 kob-odoo-19 odoo shell \\
        -c /etc/odoo/odoo.conf -d kobdb --no-http \\
        < scripts/import_uat_subcontract_boms.py

Default: DRY_RUN=1 — only prints, no writes.
"""

import json
import os

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

stats = {"created": 0, "skipped_existing": 0, "missing_product": 0,
         "missing_components": 0, "no_partner_map": 0}

for ub in boms:
    # 1) Find product template on kobdb
    tmpl = None
    if ub["tmpl_code"]:
        v = P.search([("default_code", "=", ub["tmpl_code"])], limit=1)
        if v:
            tmpl = v.product_tmpl_id
    if not tmpl:
        tmpl = T.search([("name", "=", ub["tmpl_name"])], limit=1)
    if not tmpl:
        stats["missing_product"] += 1
        continue

    # 2) Skip if subcontract BOM already exists for this product
    existing = BOM.search([
        ("product_tmpl_id", "=", tmpl.id),
        ("type", "=", "subcontract"),
    ], limit=1)
    if existing:
        stats["skipped_existing"] += 1
        continue

    # 3) Map subcontractor_ids
    mapped_subs = [PARTNER_MAP[sid] for sid in ub["sub_ids"] if sid in PARTNER_MAP]
    if not mapped_subs:
        stats["no_partner_map"] += 1
        continue

    # 4) Resolve components
    bom_lines = []
    missing = False
    for c in ub["components"]:
        comp = P.search([("default_code", "=", c["code"])], limit=1)
        if not comp:
            missing = True
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

    # 5) Create BOM
    if not DRY_RUN:
        BOM.create({
            "product_tmpl_id": tmpl.id,
            "code": ub["code"],
            "type": "subcontract",
            "subcontractor_ids": [(6, 0, mapped_subs)],
            "product_qty": ub["qty"],
            "bom_line_ids": bom_lines,
        })
    stats["created"] += 1

if not DRY_RUN:
    env.cr.commit()

print(f"Stats: {stats}")
print(f"  Total processed: {sum(stats.values())}")

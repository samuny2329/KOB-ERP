#!/usr/bin/env python3
"""Bulk-populate product unit costs + create per-company workcenters + BOMs.

  - standard_price = round(list_price * 0.35, 2)  — 35% COGS placeholder
  - 1 workcenter per company (KOB / BTV / CMN)
  - 1 operation per workcenter (30 min default)
  - 1 BOM per K/B/C-prefixed product (FG, qty 1, attached to that company's wc)
"""

env = self.env  # noqa: F821 — odoo shell

# Costs already populated in previous run; skip if already done.
already_costed = env["product.product"].search_count([("standard_price", ">", 0)])
print(f"Variants already costed: {already_costed}")

# ----- 2. Create workcenters + operations per company -----
COMPANIES = [
    (1, "KOB Production Floor",  "KOB-WC1"),
    (2, "BTV Production Floor",  "BTV-WC1"),
    (4, "CMN Production Floor",  "CMN-WC1"),
]

wc_by_company = {}
for cid, wc_name, wc_code in COMPANIES:
    company = env["res.company"].browse(cid)
    wc = env["mrp.workcenter"].search(
        [("code", "=", wc_code), ("company_id", "=", cid)], limit=1,
    )
    if not wc:
        wc = env["mrp.workcenter"].create({
            "name": wc_name,
            "code": wc_code,
            "company_id": cid,
            "resource_calendar_id": company.resource_calendar_id.id,
            "time_efficiency": 100.0,
            "costs_hour": 250.0,    # placeholder labour rate ฿/hr
            "oee_target": 85.0,
        })
        print(f"  ✓ Workcenter {wc_code} ({company.name}) created")
    else:
        print(f"  · Workcenter {wc_code} exists")
    wc_by_company[cid] = wc

env.cr.commit()

# ----- 3. Create BOMs for K-/B-/C-prefixed products -----
PREFIX_TO_COMPANY = {"K": 1, "B": 2, "C": 4}

bom_count = 0
for prefix, cid in PREFIX_TO_COMPANY.items():
    wc = wc_by_company[cid]
    products = env["product.product"].search([
        ("default_code", "=like", f"{prefix}%"),
    ])
    print(f"\n{prefix}-prefix → company {cid}: {len(products)} products")
    for p in products:
        # Skip if BOM already exists for this product+company
        existing = env["mrp.bom"].search([
            ("product_tmpl_id", "=", p.product_tmpl_id.id),
            ("company_id", "=", cid),
        ], limit=1)
        if existing:
            continue
        try:
            bom = env["mrp.bom"].create({
                "product_tmpl_id": p.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "company_id": cid,
                "code": f"BOM-{p.default_code}",
                "operation_ids": [(0, 0, {
                    "name": "Production",
                    "workcenter_id": wc.id,
                    "time_cycle_manual": 30.0,
                    "company_id": cid,
                })],
            })
            bom_count += 1
            if bom_count % 100 == 0:
                env.cr.commit()
                print(f"    · committed {bom_count} BOMs")
        except Exception as e:
            # Could fail if product is service or has cross-company constraints
            print(f"    ! skipped {p.default_code}: {e!r}"[:120])

env.cr.commit()
print(f"\n✓ Total BOMs created: {bom_count}")

# Final verification
print("\n=== Verification ===")
for cid, wc_name, _ in COMPANIES:
    wc = wc_by_company[cid]
    bom_n = env["mrp.bom"].search_count([("company_id", "=", cid)])
    op_n = env["mrp.routing.workcenter"].search_count([("company_id", "=", cid)])
    print(f"  Company {cid}: wc={wc.name} | BOMs={bom_n} | Operations={op_n}")

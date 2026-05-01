# -*- coding: utf-8 -*-
"""Seed 2 companies + their warehouses (mirror UAT structure)."""

# Rename Company 1
c1 = env["res.company"].browse(1)
c1.write({"name": "Kiss of Beauty Co., Ltd."})

# Create Company 2 if not exists
c2 = env["res.company"].search([("name", "=", "Kiss of Beauty CMN Co., Ltd.")], limit=1)
if not c2:
    c2 = env["res.company"].create({
        "name": "Kiss of Beauty CMN Co., Ltd.",
        "currency_id": c1.currency_id.id,
    })

# Make admin a member of both companies
admin = env["res.users"].browse(2)
admin.company_ids = [(4, c1.id), (4, c2.id)]

# Default warehouse renaming + creation
wh1 = env["stock.warehouse"].search([("company_id", "=", c1.id)], limit=1)
if wh1:
    wh1.write({"name": "KOB Online WH", "code": "KOB"})

# Online + Offline warehouses for Company 1
wh1b = env["stock.warehouse"].search([
    ("company_id", "=", c1.id),
    ("code", "=", "OFL"),
], limit=1)
if not wh1b:
    wh1b = env["stock.warehouse"].sudo().create({
        "company_id": c1.id,
        "name": "KOB Offline WH",
        "code": "OFL",
    })

# Warehouse for Company 2
wh2 = env["stock.warehouse"].search([("company_id", "=", c2.id)], limit=1)
if not wh2:
    wh2 = env["stock.warehouse"].sudo().create({
        "company_id": c2.id,
        "name": "CMN Packaging WH",
        "code": "CMN",
    })

env.cr.commit()

print(f"\n=== COMPANIES + WAREHOUSES ===")
for c in env["res.company"].search([], order="id"):
    whs = env["stock.warehouse"].search([("company_id", "=", c.id)])
    print(f"  Company {c.id}: {c.name}")
    for w in whs:
        print(f"    Warehouse: [{w.code}] {w.name}")

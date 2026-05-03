"""Align local kobdb warehouse/route/location config to match UAT
(`kiss-production_2026-03-09` snapshot from 2026-05-03).

Reverts earlier ad-hoc changes that diverged from UAT:
- Clear `resupply_wh_ids` on KISS+BTV warehouses
- Reactivate per-warehouse Resupply Subcontractor routes
- Reduce `product_selectable=True` to only KOB-WH1 + shared "on Order"
- Set K-Off sequence=0
- B-Off + CMN-WH reception_steps=three_steps
- Create shared "Physical Locations" view

Reference: reports/product_audit_2026-05-03/UAT_WAREHOUSE_CONTEXT.md

Run via:
    docker exec -i kob-odoo-19 odoo shell -c /etc/odoo/odoo.conf -d kobdb \\
        --no-http < scripts/align_kobdb_to_uat.py

Set DRY_RUN=0 env var to actually write. Default is dry-run.
"""

import os

DRY_RUN = os.environ.get("DRY_RUN", "1") != "0"

WH = env["stock.warehouse"]
Route = env["stock.route"]
Loc = env["stock.location"]

print(f"=== {'EXECUTE' if not DRY_RUN else 'DRY RUN (set DRY_RUN=0 to apply)'} ===\n")

# Step 5a: B-Off three_steps
boff = WH.search([("code", "=", "B-Off")], limit=1)
print(f"Step 5a: B-Off reception={boff.reception_steps} → three_steps")
if not DRY_RUN and boff.reception_steps != "three_steps":
    boff.write({"reception_steps": "three_steps"})

# Step 5b: CMN-WH three_steps
cmnw = WH.search([("code", "=", "CMNW")], limit=1)
print(f"Step 5b: CMN-WH reception={cmnw.reception_steps} → three_steps")
if not DRY_RUN and cmnw.reception_steps != "three_steps":
    cmnw.write({"reception_steps": "three_steps"})

# Step 4: K-Off seq=0
koff = WH.search([("code", "=", "K-Off")], limit=1)
print(f"Step 4: K-Off seq={koff.sequence} → 0")
if not DRY_RUN and koff.sequence != 0:
    koff.write({"sequence": 0})

# Step 1: Clear resupply_wh_ids
all_kb = WH.search([("company_id", "in", [1, 2])])
to_clear = all_kb.filtered(lambda w: w.resupply_wh_ids)
print(f"Step 1: Clear resupply_wh_ids on {len(to_clear)} warehouses (of {len(all_kb)} KISS+BTV)")
if not DRY_RUN:
    to_clear.write({"resupply_wh_ids": [(5, 0, 0)]})

# Step 2: Reactivate inactive subcontract routes
inactive = Route.search([("name", "ilike", "Resupply Subcontractor"), ("active", "=", False)])
print(f"Step 2: Reactivate {len(inactive)} subcontract routes")
if not DRY_RUN and inactive:
    inactive.write({"active": True})

# Step 3: product_selectable=True only on KOB-WH1 + shared "on Order"
all_sub = Route.search([("name", "ilike", "Resupply Subcontractor")])
keep = Route.search([
    ("name", "in", [
        "KOB-WH1 (Offline): Resupply Subcontractor",
        "Resupply Subcontractor on Order",
    ])
])
to_unselect = (all_sub - keep).filtered(lambda r: r.product_selectable)
print(f"Step 3: Unselect {len(to_unselect)}, keep selectable: {keep.mapped('name')}")
if not DRY_RUN:
    to_unselect.write({"product_selectable": False})
    keep.filtered(lambda r: not r.product_selectable).write({"product_selectable": True})

# Step 6: Create Physical Locations view (shared)
phys = Loc.search([
    ("name", "=", "Physical Locations"),
    ("usage", "=", "view"),
    ("company_id", "=", False),
], limit=1)
if not phys:
    print(f"Step 6: Create 'Physical Locations' view (shared)")
    if not DRY_RUN:
        phys = Loc.create({"name": "Physical Locations", "usage": "view", "company_id": False})
        print(f"  Created id={phys.id}")
else:
    print(f"Step 6: Physical Locations view already exists (id={phys.id})")

# Note: Subcontracting reparent blocked by mrp_subcontracting._check_subcontracting_location

if not DRY_RUN:
    env.cr.commit()
    print("\n=== ALL STEPS COMMITTED ===")
else:
    print("\n=== DRY RUN — run with DRY_RUN=0 to commit ===")

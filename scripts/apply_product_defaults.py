"""Apply standardized Operations + Counterpart Locations to FG products.

Scope: saleable + purchasable + shared (company_id=False) + active product
templates. Skips RM / Service / Expense per business decision.

Target settings (from KLC226 reference in UAT):
  - route_ids = [Buy, Manufacture]
  - property_stock_production = company's "Virtual Locations/Production"
  - property_stock_inventory  = company's "Virtual Locations/Inventory adjustment"

Run via:
    docker exec kob-odoo-19 odoo shell -c /etc/odoo/odoo.conf -d <DB> \\
        --no-http < scripts/apply_product_defaults.py

Defaults to DRY_RUN. To execute writes, set env:
    DRY_RUN=0 docker exec ...
"""

import os

DRY_RUN = os.environ.get("DRY_RUN", "1") != "0"

Template = env["product.template"]
Route = env["stock.route"]
Location = env["stock.location"]
Company = env["res.company"]
Attachment = env["ir.attachment"]

# 1. Resolve target route IDs by name (avoid hardcoded IDs across DBs)
buy = Route.search([("name", "=", "Buy")], limit=1)
manufacture = Route.search([("name", "=", "Manufacture")], limit=1)
assert buy and manufacture, "Missing 'Buy' or 'Manufacture' route — check Odoo install"
target_route_ids = [buy.id, manufacture.id]
print(f"Target routes: Buy(id={buy.id}) + Manufacture(id={manufacture.id})")

# 1b. Ensure target routes are product_selectable (else Odoo silently filters them
# out when written to product.template.route_ids).
to_flip = (buy + manufacture).filtered(lambda r: not r.product_selectable)
if to_flip:
    if DRY_RUN:
        print(f"  WOULD set product_selectable=True on: {to_flip.mapped('name')}")
    else:
        to_flip.write({"product_selectable": True})
        print(f"  ✓ Set product_selectable=True on: {to_flip.mapped('name')}")

# 2. Build per-company virtual location map
companies = Company.search([])
loc_map = {}  # cid -> {production, inventory}
for co in companies:
    prod = Location.search([
        ("company_id", "=", co.id),
        ("name", "=", "Production"),
        ("usage", "=", "production"),
    ], limit=1)
    inv = Location.search([
        ("company_id", "=", co.id),
        ("name", "=", "Inventory adjustment"),
        ("usage", "=", "inventory"),
    ], limit=1)
    if prod and inv:
        loc_map[co.id] = {"production": prod.id, "inventory": inv.id}
        print(f"  co={co.id} {co.name}: prod={prod.id} inv={inv.id}")
    else:
        print(f"  co={co.id} {co.name}: MISSING virtual location — skipping")

# 3. Find scope: FG-equivalent (saleable+purchasable+shared+active)
scope = Template.search([
    ("active", "=", True),
    ("company_id", "=", False),
    ("sale_ok", "=", True),
    ("purchase_ok", "=", True),
])
needs_route_change = scope.filtered(
    lambda t: sorted(t.route_ids.ids) != sorted(target_route_ids)
)
print(f"\nScope: {len(scope)} templates ({len(needs_route_change)} need route change)")

# 4. Backup current state to ir.attachment (CSV)
import csv, io, base64
buf = io.StringIO()
w = csv.writer(buf)
header = ["id", "default_code", "name", "route_ids"]
for cid in loc_map:
    header += [f"co{cid}_prod", f"co{cid}_inv"]
w.writerow(header)
for t in scope:
    row = [t.id, t.default_code or "", t.name, "|".join(map(str, t.route_ids.ids))]
    for cid in loc_map:
        tc = t.with_company(cid)
        row += [
            tc.property_stock_production.id if tc.property_stock_production else "",
            tc.property_stock_inventory.id if tc.property_stock_inventory else "",
        ]
    w.writerow(row)
csv_bytes = buf.getvalue().encode("utf-8")
print(f"Backup CSV: {len(csv_bytes)} bytes")

if DRY_RUN:
    print("\n=== DRY RUN — no writes performed ===")
    print(f"Would update route_ids on {len(needs_route_change)} templates")
    print(f"Would force property_stock_* on {len(scope)} templates × "
          f"{len(loc_map)} companies = {len(scope) * len(loc_map)} writes")
    print("Set DRY_RUN=0 to execute.")
else:
    # Save backup attachment first
    att = Attachment.create({
        "name": "BACKUP_apply_product_defaults.csv",
        "type": "binary",
        "datas": base64.b64encode(csv_bytes).decode("ascii"),
        "mimetype": "text/csv",
        "description": "Backup before apply_product_defaults.py write",
    })
    print(f"Backup saved: ir.attachment id={att.id}")

    # Bulk update route_ids
    if needs_route_change:
        needs_route_change.write({"route_ids": [(6, 0, target_route_ids)]})
        print(f"✓ Updated route_ids on {len(needs_route_change)} templates")

    # Force counterpart locations per company
    for cid, locs in loc_map.items():
        scope.with_company(cid).write({
            "property_stock_production": locs["production"],
            "property_stock_inventory": locs["inventory"],
        })
        print(f"✓ co={cid}: forced counterpart on {len(scope)} templates")

    env.cr.commit()
    print("\n=== DONE ===")

#!/usr/bin/env python3
"""Rebuild BOMs from scratch:
  1. Enable Work-Order Operations group (Operations tab visible on BOM)
  2. Drop existing 3,690 placeholder BOMs (no components)
  3. For each FG product (default_code with no '-' suffix):
       - Find sibling products sharing same base prefix → use as BOM components
       - Create BOM on each of 3 companies (1=KOB, 2=BTV, 4=CMN) using that
         company's workcenter for the Production operation
       - Reference = product default_code (no 'BOM-' prefix)
  4. Skip components themselves (codes containing '-XX-NN' patterns)

Result: ~hundreds of FG products × 3 companies × N components each.
"""

import re

env = self.env  # noqa: F821

# ----- 0. Enable Work-Orders group on every internal user -----
group = env.ref("mrp.group_mrp_routings")
internal = env.ref("base.group_user")
internal.write({"implied_ids": [(4, group.id)]})
print(f"✓ group_mrp_routings ({group.id}) implied by group_user")
# also explicitly add admin
try:
    admin = env.ref("base.user_admin", raise_if_not_found=False) or env.ref("base.user_root")
    # Odoo 19: try both group_ids (new) and groups_id (legacy)
    if "group_ids" in env["res.users"]._fields:
        admin.write({"group_ids": [(4, group.id)]})
    else:
        admin.sudo().write({"groups_id": [(4, group.id)]})
    print(f"✓ admin granted Work-Order Operations")
except Exception as e:
    print(f"  ! admin grant skipped: {e!r}"[:120])

# ----- 1. Get workcenters per company -----
WC_BY_CO = {}
for code, cid in [("KOB-WC1", 1), ("BTV-WC1", 2), ("CMN-WC1", 4)]:
    wc = env["mrp.workcenter"].search([("code", "=", code)], limit=1)
    if wc:
        WC_BY_CO[cid] = wc
print(f"Workcenters: {[(c, w.name) for c, w in WC_BY_CO.items()]}")

# ----- 2. Drop existing BOMs (placeholder, no components) -----
old = env["mrp.bom"].search([])
print(f"Removing {len(old)} existing BOMs...")
old.unlink()
env.cr.commit()
print(f"  ✓ removed")

# ----- 3. Identify FG products vs components by SKU pattern -----
# Components match patterns like:
#   FOO-CT-01, FOO-JA-01, FOO-ST-03, FOO-CL, FOO-BX-01, FOO-PB-01 etc.
# An FG is anything that does NOT have those component-type suffixes.
COMPONENT_SUFFIX_RE = re.compile(
    r'^(?P<base>[A-Z0-9]+)-(CL|CT|JA|ST|BX|PB|TT|LB|FT|BT|SP|PG|TG|TS|WT)\b',
    re.IGNORECASE,
)

all_pt = env["product.template"].search([("default_code", "!=", False)])
print(f"\nTotal coded products: {len(all_pt)}")

base_to_components = {}
fg_products = []
for pt in all_pt:
    code = pt.default_code or ""
    m = COMPONENT_SUFFIX_RE.match(code)
    if m:
        base = m.group("base")
        base_to_components.setdefault(base, []).append(pt)
    else:
        fg_products.append(pt)

print(f"  Identified {len(fg_products)} FG products + "
      f"{sum(len(v) for v in base_to_components.values())} components "
      f"across {len(base_to_components)} bases")

# ----- 4. Build BOMs -----
created = 0
skipped = 0
for fg in fg_products:
    code = fg.default_code
    components = base_to_components.get(code, [])
    for cid, wc in WC_BY_CO.items():
        try:
            vals = {
                "product_tmpl_id": fg.id,
                "product_qty": 1.0,
                "type": "normal",
                "company_id": cid,
                "code": code,  # no BOM- prefix
                "operation_ids": [(0, 0, {
                    "name": "Production",
                    "workcenter_id": wc.id,
                    "time_cycle_manual": 30.0,
                    "company_id": cid,
                })],
            }
            if components:
                vals["bom_line_ids"] = [
                    (0, 0, {
                        "product_id": comp.product_variant_id.id,
                        "product_qty": 1.0,
                        "company_id": cid,
                    })
                    for comp in components
                ]
            env["mrp.bom"].create(vals)
            created += 1
        except Exception as e:
            skipped += 1
            if skipped <= 3:
                print(f"    ! skip {code} co{cid}: {e!r}"[:140])
    if created % 200 == 0 and created > 0:
        env.cr.commit()

env.cr.commit()
print(f"\n✓ {created} BOMs created · {skipped} skipped")

# ----- 5. Final report -----
print("\n=== Final state ===")
for cid in [1, 2, 4]:
    co = env["res.company"].browse(cid)
    n = env["mrp.bom"].search_count([("company_id", "=", cid)])
    print(f"  co{cid} {co.name}: {n} BOMs")

# AVH290 verification
avh = env["mrp.bom"].search([("code", "=", "AVH290")])
print(f"\n  AVH290 BOMs: {len(avh)} (expected 3)")
for b in avh:
    print(f"    co{b.company_id.id} | {b.code} | "
          f"{len(b.bom_line_ids)} components | "
          f"{len(b.operation_ids)} operations")

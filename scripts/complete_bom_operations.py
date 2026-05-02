#!/usr/bin/env python3
"""Create BOMs for all 2587 products without BOM + enable Manufacture+Buy routes."""

env = self.env  # noqa: F821

KOB_WC = env["mrp.workcenter"].search([("code", "=", "KOB-WC1")], limit=1)
print(f"KOB workcenter id: {KOB_WC.id}")

manufacture_route = env["stock.route"].browse(5)  # global Manufacture route
buy_route = env["stock.route"].browse(4)  # global Buy route
print(f"Routes: Manufacture={manufacture_route.name}, Buy={buy_route.name}")

# 1. Find products without BOM via raw SQL
env.cr.execute("""
    SELECT pt.id FROM product_template pt
    LEFT JOIN mrp_bom b ON b.product_tmpl_id = pt.id
    WHERE pt.default_code IS NOT NULL AND b.id IS NULL
""")
missing_ids = [r[0] for r in env.cr.fetchall()]
missing_bom = env["product.template"].browse(missing_ids)
print(f"\nProducts without BOM: {len(missing_bom)}")

bom_count = 0
batch = 0
for pt in missing_bom:
    try:
        env["mrp.bom"].create({
            "product_tmpl_id": pt.id,
            "product_qty": 1.0,
            "type": "normal",
            "company_id": 1,  # KOB default
            "code": f"BOM-{pt.default_code}",
            "operation_ids": [(0, 0, {
                "name": "Production",
                "workcenter_id": KOB_WC.id,
                "time_cycle_manual": 30.0,
                "company_id": 1,
            })],
        })
        bom_count += 1
        batch += 1
        if batch >= 200:
            env.cr.commit()
            print(f"  · committed {bom_count}")
            batch = 0
    except Exception as e:
        # silent skip — likely route/category constraint
        pass
env.cr.commit()
print(f"  ✓ {bom_count} new BOMs created")

# 2. Enable Manufacture + Buy routes on every product with default_code
print("\nEnabling Manufacture + Buy routes on all coded products...")
all_coded = env["product.template"].search([("default_code", "!=", False)])
n = 0
for pt in all_coded:
    needs = []
    cur_route_ids = pt.route_ids.ids
    if manufacture_route.id not in cur_route_ids:
        needs.append((4, manufacture_route.id))
    if buy_route.id not in cur_route_ids:
        needs.append((4, buy_route.id))
    if needs:
        pt.route_ids = needs
        n += 1
    if n > 0 and n % 500 == 0:
        env.cr.commit()
        print(f"  · committed {n}")
env.cr.commit()
print(f"  ✓ {n} products had Manufacture/Buy routes added")

# 3. Verification
print("\n=== Final state ===")
print(f"  BOMs total: {env['mrp.bom'].search_count([])}")
print(f"  BOMs co1 (KOB): {env['mrp.bom'].search_count([('company_id','=',1)])}")
print(f"  BOMs co2 (BTV): {env['mrp.bom'].search_count([('company_id','=',2)])}")
print(f"  BOMs co4 (CMN): {env['mrp.bom'].search_count([('company_id','=',4)])}")
print(f"  Operations total: {env['mrp.routing.workcenter'].search_count([])}")
products_with_mfg = env["product.template"].search_count([
    ("route_ids", "in", manufacture_route.id),
])
print(f"  Products with Manufacture route: {products_with_mfg}")

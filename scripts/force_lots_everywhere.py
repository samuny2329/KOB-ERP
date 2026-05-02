#!/usr/bin/env python3
"""Force lot tracking + auto-create lots for every non-zero quant.

  1. tracking='lot' on every product (override via SQL when quants exist)
  2. use_expiration_date=True with expiration_time=1095 (3 years) for FEFO
  3. For every quant.lot_id IS NULL — create stock.lot named
       LOT-{default_code}-{YYMMDD} with random expiration 6-36 months out
     and assign all matching quants to that lot
  4. For all DOs in 'assigned'/'confirmed' state — do_unreserve + action_assign
     to refresh move_lines with new lot info
"""

import random
from datetime import date, timedelta

env = self.env  # noqa: F821
random.seed(42)

# ----- 1. SQL force tracking on every coded product -----
env.cr.execute("""
    UPDATE product_template
    SET tracking = 'lot',
        use_expiration_date = TRUE,
        expiration_time = 1095
    WHERE default_code IS NOT NULL AND tracking != 'lot'
""")
n_changed = env.cr.rowcount
env.cr.commit()
print(f"  ✓ tracking='lot' forced on {n_changed} products")

# Invalidate ORM cache so Odoo sees the updated values
env["product.template"].invalidate_model(["tracking", "use_expiration_date", "expiration_time"])

# ----- 2. Create lots for every distinct product with quant.lot_id IS NULL -----
env.cr.execute("""
    SELECT DISTINCT q.product_id
    FROM stock_quant q
    WHERE q.lot_id IS NULL
      AND q.quantity > 0
""")
products_needing_lot = [r[0] for r in env.cr.fetchall()]
print(f"\n  Products with un-lotted quants: {len(products_needing_lot)}")

today = date.today()
lot_count = 0
for pid in products_needing_lot:
    pp = env["product.product"].browse(pid)
    code = pp.default_code or f"P{pid}"
    # Create one lot per product with random future expiration
    months_out = random.randint(6, 36)
    expire = today + timedelta(days=months_out * 30)
    try:
        lot = env["stock.lot"].create({
            "name": f"LOT-{code}-{today.strftime('%y%m%d')}",
            "product_id": pid,
            "expiration_date": expire,
            "company_id": pp.company_id.id or 1,
        })
        # Link all quants for this product (no lot yet) to this lot
        env.cr.execute("""
            UPDATE stock_quant
            SET lot_id = %s
            WHERE product_id = %s AND lot_id IS NULL AND quantity > 0
        """, (lot.id, pid))
        lot_count += 1
    except Exception as e:
        if lot_count < 3:
            print(f"  ! lot create skipped {code}: {e!r}"[:120])

env.cr.commit()
print(f"  ✓ {lot_count} lots created and linked to quants")

# ----- 3. Refresh existing Ready / Confirmed DOs -----
pickings = env["stock.picking"].search([
    ("state", "in", ("confirmed", "assigned", "partially_available")),
    ("picking_type_id.code", "=", "outgoing"),
])
print(f"\n  DOs to refresh: {len(pickings)}")
refreshed = 0
for p in pickings:
    try:
        p.do_unreserve()
        p.action_assign()
        refreshed += 1
    except Exception as e:
        pass
env.cr.commit()
print(f"  ✓ {refreshed} DOs unreserved + re-reserved")

# ----- 4. Final verification -----
print("\n=== Verification ===")
env.cr.execute("""
    SELECT COUNT(*) FILTER (WHERE lot_id IS NOT NULL) as with_lot,
           COUNT(*) FILTER (WHERE lot_id IS NULL) as no_lot,
           COUNT(*) as total
    FROM stock_quant WHERE quantity > 0
""")
with_lot, no_lot, total = env.cr.fetchone()
print(f"  Quants: {with_lot} with lot · {no_lot} without · {total} total")

env.cr.execute("""
    SELECT COUNT(*) FROM product_template WHERE tracking='lot' AND default_code IS NOT NULL
""")
print(f"  Lot-tracked products: {env.cr.fetchone()[0]}")

env.cr.execute("SELECT COUNT(*) FROM stock_lot")
print(f"  Total stock_lot records: {env.cr.fetchone()[0]}")

# Sample DUT300
dut = env["product.product"].search([("default_code", "=", "DUT300")], limit=1)
if dut:
    quants = env["stock.quant"].search([("product_id", "=", dut.id), ("quantity", ">", 0)])
    print(f"\n  DUT300: {len(quants)} quants")
    for q in quants[:3]:
        print(f"    {q.location_id.complete_name} | qty={q.quantity} | lot={q.lot_id.name or '—'}")

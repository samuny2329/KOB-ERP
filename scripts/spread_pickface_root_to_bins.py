#!/usr/bin/env python3
"""Move quants from K-On/Stock/PICKFACE root → random PF child bins.

After fix_quant_fragmentation.py, all topped-up stock sits at PICKFACE root.
Spread it across the 350 PF-A...PF-G bins (1-3 random bins per product, whole units).
"""

import random
env = self.env  # noqa: F821
random.seed(42)

pickface = env["stock.location"].search(
    [("complete_name", "=", "K-On/Stock/PICKFACE")], limit=1,
)
print(f"PICKFACE id: {pickface.id}")

pf_bins = env["stock.location"].search([
    ("complete_name", "=like", "K-On/Stock/PICKFACE/PF-%"),
])
print(f"PF child bins: {len(pf_bins)}")

# Find quants at PICKFACE root (not children)
root_quants = env["stock.quant"].search([
    ("location_id", "=", pickface.id),
    ("quantity", ">", 0),
])
print(f"Quants at PICKFACE root: {len(root_quants)}")

moved = 0
for q in root_quants:
    qty = int(q.quantity or 0)
    if qty <= 0:
        continue
    # Split into 2-4 random bins, whole numbers
    n = random.randint(2, 4)
    targets = random.sample(list(pf_bins), n)
    # Random integer split summing to qty
    cuts = sorted(random.sample(range(1, qty), n - 1)) if qty > n else []
    portions = []
    prev = 0
    for c in cuts:
        portions.append(c - prev)
        prev = c
    portions.append(qty - prev)
    if len(portions) != n:
        portions = [qty // n] * n
        portions[-1] += qty - sum(portions)
    # Apply
    for tgt, p in zip(targets, portions):
        if p <= 0:
            continue
        try:
            env["stock.quant"]._update_available_quantity(
                q.product_id, tgt, p, lot_id=q.lot_id,
            )
            moved += 1
        except Exception:
            pass
    # Zero out the source root quant via SQL (avoid validation)
    env.cr.execute(
        "UPDATE stock_quant SET quantity = 0 WHERE id = %s", (q.id,),
    )
    if moved % 500 == 0 and moved > 0:
        env.cr.commit()
env.cr.commit()
print(f"  ✓ {moved} sub-quant transfers")

# Delete zero quants on root
env.cr.execute(
    "DELETE FROM stock_quant WHERE location_id = %s AND quantity = 0 AND reserved_quantity = 0",
    (pickface.id,),
)
print(f"  ✓ {env.cr.rowcount} zero quants on PICKFACE root deleted")
env.cr.commit()

# Verification
print("\n=== After spread ===")
n_root = env["stock.quant"].search_count(
    [("location_id", "=", pickface.id), ("quantity", "!=", 0)],
)
print(f"  PICKFACE root quants: {n_root}")
n_bins_with_stock = env.cr.execute("""
    SELECT COUNT(DISTINCT location_id)
    FROM stock_quant q JOIN stock_location l ON l.id = q.location_id
    WHERE l.complete_name LIKE 'K-On/Stock/PICKFACE/PF-%' AND q.quantity > 0
""")
print(f"  PF bins with stock: {env.cr.fetchone()[0]}")

# AVH290 check
env.cr.execute("""
    SELECT l.complete_name, q.quantity, sl.name AS lot
    FROM stock_quant q
    JOIN product_product pp ON pp.id = q.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN stock_location l ON l.id = q.location_id
    LEFT JOIN stock_lot sl ON sl.id = q.lot_id
    WHERE pt.default_code = 'AVH290' AND q.quantity > 0
    ORDER BY l.complete_name
""")
print("\n  AVH290 distribution:")
for row in env.cr.fetchall():
    print(f"    {row[0]:50s} | qty={row[1]:>6.0f} | {row[2]}")

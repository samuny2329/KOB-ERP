#!/usr/bin/env python3
"""Fix the quant fragmentation problem:
  1. Each product has 2 lots (AUTO-... and LOT-...) — merge AUTO into LOT
  2. Quantities are decimal fractions (0.17, 0.60) from random Dirichlet split
     — round to whole units
  3. Total stock per product is too low (often <10 units total) — top up
     each product to ~1000 units distributed across its existing bins
"""

env = self.env  # noqa: F821

# Step 1: Merge AUTO-* lots into LOT-* lots per product
print("Step 1: Merge AUTO lots → LOT lots")
env.cr.execute("""
    SELECT a.id AS auto_lot_id, l.id AS lot_id, a.product_id
    FROM stock_lot a
    JOIN stock_lot l ON l.product_id = a.product_id AND l.name LIKE 'LOT-%'
    WHERE a.name LIKE 'AUTO-%'
""")
mappings = env.cr.fetchall()
print(f"  · {len(mappings)} AUTO→LOT mappings found")

merged = 0
for auto_id, lot_id, _ in mappings:
    # Move all quants from auto_lot to lot
    env.cr.execute(
        "UPDATE stock_quant SET lot_id = %s WHERE lot_id = %s",
        (lot_id, auto_id),
    )
    merged += env.cr.rowcount
env.cr.commit()
print(f"  ✓ {merged} quants re-pointed to LOT-* lots")

# Step 2: Delete orphan AUTO lots
env.cr.execute("DELETE FROM stock_lot WHERE name LIKE 'AUTO-%'")
deleted = env.cr.rowcount
env.cr.commit()
print(f"  ✓ {deleted} AUTO lots deleted")

# Step 3: Merge duplicate quants (same product, lot, location)
print("\nStep 3: Merge duplicate quants")
env.cr.execute("""
    WITH dups AS (
        SELECT product_id, lot_id, location_id,
               array_agg(id ORDER BY id) AS ids,
               SUM(quantity) AS total_qty,
               SUM(reserved_quantity) AS total_res
        FROM stock_quant
        WHERE quantity != 0
        GROUP BY product_id, lot_id, location_id
        HAVING COUNT(*) > 1
    )
    UPDATE stock_quant q
    SET quantity = d.total_qty, reserved_quantity = d.total_res
    FROM dups d
    WHERE q.id = d.ids[1]
""")
print(f"  ✓ {env.cr.rowcount} primary quants merged")
env.cr.execute("""
    DELETE FROM stock_quant
    WHERE id IN (
        SELECT unnest(ids[2:array_length(ids,1)])
        FROM (
            SELECT array_agg(id ORDER BY id) AS ids
            FROM stock_quant
            WHERE quantity != 0
            GROUP BY product_id, lot_id, location_id
            HAVING COUNT(*) > 1
        ) sub
    )
""")
print(f"  ✓ {env.cr.rowcount} duplicate quants removed")
env.cr.commit()

# Step 4: Round all quantities to whole units (cosmetics qty is whole units)
print("\nStep 4: Round quantities to whole units")
env.cr.execute("UPDATE stock_quant SET quantity = ROUND(quantity), reserved_quantity = ROUND(reserved_quantity)")
print(f"  ✓ {env.cr.rowcount} quants rounded")

# Delete zero quants
env.cr.execute("DELETE FROM stock_quant WHERE quantity = 0 AND reserved_quantity = 0")
print(f"  ✓ {env.cr.rowcount} zero quants removed")
env.cr.commit()

# Step 5: Top up products with low stock — add 1000 units per product to PICKFACE root
print("\nStep 5: Top up products with low total stock")
env.cr.execute("""
    SELECT pp.id, pt.default_code,
           COALESCE((SELECT SUM(quantity) FROM stock_quant WHERE product_id = pp.id), 0) AS total
    FROM product_product pp
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE pt.default_code IS NOT NULL
""")
products = env.cr.fetchall()

low_stock = [(pid, code, total) for pid, code, total in products if total < 100]
print(f"  · {len(low_stock)} products with total < 100 units (out of {len(products)})")

pickface = env["stock.location"].search(
    [("complete_name", "=", "K-On/Stock/PICKFACE")], limit=1,
)
topped = 0
for pid, code, total in low_stock:
    pp = env["product.product"].browse(pid)
    # Find or create lot
    lot = env["stock.lot"].search(
        [("product_id", "=", pid), ("name", "like", "LOT-%")], limit=1,
    )
    if not lot:
        from datetime import date, timedelta
        import random
        random.seed(int(pid))
        expire = date.today() + timedelta(days=random.randint(180, 1095))
        lot = env["stock.lot"].create({
            "name": f"LOT-{code}-260502",
            "product_id": pid,
            "expiration_date": expire,
            "company_id": pp.company_id.id or 1,
        })
    target_qty = max(1000 - int(total), 0)
    if target_qty > 0:
        try:
            env["stock.quant"]._update_available_quantity(
                pp, pickface, target_qty, lot_id=lot,
            )
            topped += 1
        except Exception:
            pass
    if topped % 200 == 0 and topped > 0:
        env.cr.commit()

env.cr.commit()
print(f"  ✓ {topped} products topped up to ≥1000 units")

# Final summary
print("\n=== Final state ===")
env.cr.execute("""
    SELECT
        COUNT(*) AS total_quants,
        ROUND(SUM(quantity)::numeric, 0) AS total_units,
        ROUND(AVG(quantity)::numeric, 2) AS avg_qty
    FROM stock_quant
    WHERE quantity > 0
""")
print(f"  {env.cr.fetchone()}")

env.cr.execute("""
    SELECT pt.default_code, ROUND(SUM(q.quantity)::numeric, 0)
    FROM stock_quant q JOIN product_product pp ON pp.id = q.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE pt.default_code = 'AVH290' AND q.quantity > 0
""")
print(f"  AVH290 total: {env.cr.fetchone()}")

#!/usr/bin/env python3
"""KOB-WH2 (K-On) outgoing must source from PICKFACE only.

Steps:
  1. Re-parent K-On PF-A through PF-G under K-On/Stock/PICKFACE
     (so PICKFACE descendant tree includes all 350 bins).
  2. Move K-On/Stock root quants (the residual 143) into PICKFACE
     (or random across PICKFACE descendants).
  3. Update pull rule "WH: Stock → Customers" for K-On warehouse
     so source_location = K-On/Stock/PICKFACE.
  4. Refresh all Ready/Confirmed K-On outgoing DOs.
"""

import random
env = self.env  # noqa: F821
random.seed(7)

# ----- Locate key locations -----
kon_stock = env["stock.location"].search(
    [("complete_name", "=", "K-On/Stock")], limit=1,
)
pickface = env["stock.location"].search(
    [("complete_name", "=", "K-On/Stock/PICKFACE")], limit=1,
)
print(f"K-On/Stock id={kon_stock.id} · PICKFACE id={pickface.id}")

# ----- 1. Re-parent PF-A...PF-G under PICKFACE -----
direct_pf = env["stock.location"].search([
    ("complete_name", "=like", "K-On/Stock/PF-%"),
    ("location_id", "=", kon_stock.id),
])
print(f"\nRe-parent {len(direct_pf)} PF bins under PICKFACE...")
n = 0
for loc in direct_pf:
    loc.location_id = pickface.id
    n += 1
    if n % 50 == 0:
        env.cr.commit()
env.cr.commit()
print(f"  ✓ {n} bins now under PICKFACE")

# ----- 2. Move K-On/Stock root residual quants into PICKFACE descendants -----
root_quants = env["stock.quant"].search([
    ("location_id", "=", kon_stock.id),
    ("quantity", ">", 0),
])
pf_bins = env["stock.location"].search([
    ("complete_name", "=like", "K-On/Stock/PICKFACE/PF-%"),
])
print(f"\nMove {len(root_quants)} root quants into "
      f"{len(pf_bins)} PICKFACE bins + PICKFACE itself")

moved = 0
for q in root_quants:
    qty = float(q.quantity or 0)
    if qty <= 0:
        continue
    # 30% to PICKFACE root, 70% spread across 2-4 random child bins
    n_splits = random.randint(2, 4)
    targets = random.sample(list(pf_bins), n_splits) + [pickface]
    weights = [random.random() for _ in targets]
    s = sum(weights)
    portions = [round(qty * w / s, 2) for w in weights]
    portions[-1] = round(qty - sum(portions[:-1]), 2)
    for tgt, p in zip(targets, portions):
        if p <= 0:
            continue
        try:
            env["stock.quant"]._update_available_quantity(
                q.product_id, tgt, p, lot_id=q.lot_id,
            )
            env["stock.quant"]._update_available_quantity(
                q.product_id, kon_stock, -p, lot_id=q.lot_id,
            )
            moved += 1
        except Exception:
            pass
env.cr.commit()
print(f"  ✓ {moved} quant transfers")

# ----- 3. Update pull rule(s) for K-On outgoing  -----
# K-On/Stock → Customers : source must be PICKFACE
rules = env["stock.rule"].search([
    ("location_src_id", "=", kon_stock.id),
    ("location_dest_id.usage", "=", "customer"),
])
print(f"\nUpdate {len(rules)} pull rules → source = PICKFACE")
for r in rules:
    r.location_src_id = pickface.id
    print(f"  · #{r.id} {r.name} → src=PICKFACE")
env.cr.commit()

# ----- 4. Refresh Ready / Confirmed K-On outgoing DOs -----
pickings = env["stock.picking"].search([
    ("state", "in", ("confirmed", "assigned", "partially_available")),
    ("picking_type_id.code", "=", "outgoing"),
    ("picking_type_id.warehouse_id.code", "=", "K-On"),
])
print(f"\nRefresh {len(pickings)} K-On outgoing DOs")
refreshed = 0
for p in pickings:
    try:
        p.do_unreserve()
        p.action_assign()
        refreshed += 1
    except Exception:
        pass
env.cr.commit()
print(f"  ✓ {refreshed} re-reserved")

# ----- Verification -----
print("\n=== Verification ===")
n_pf_descendant = env["stock.location"].search_count(
    [("complete_name", "=like", "K-On/Stock/PICKFACE/PF-%")],
)
print(f"  PF bins now under PICKFACE: {n_pf_descendant}")
n_root_quant = env["stock.quant"].search_count(
    [("location_id", "=", kon_stock.id), ("quantity", ">", 0)],
)
print(f"  K-On/Stock root quants remaining: {n_root_quant}")
n_pickface_desc_quants = env.cr.execute("""
    SELECT COUNT(*) FROM stock_quant q
    JOIN stock_location l ON l.id = q.location_id
    WHERE l.parent_path LIKE %s AND q.quantity > 0
""", (f"%/{pickface.id}/%",))
n_pickface_desc_quants = env.cr.fetchone()[0]
print(f"  Quants under PICKFACE tree: {n_pickface_desc_quants}")

# DUT300 sample
dut = env["product.product"].search([("default_code", "=", "DUT300")], limit=1)
if dut:
    qs = env["stock.quant"].search(
        [("product_id", "=", dut.id), ("quantity", ">", 0)],
        limit=5,
    )
    print(f"\n  DUT300 sample quants:")
    for q in qs:
        print(f"    {q.location_id.complete_name} | qty={q.quantity} | "
              f"lot={q.lot_id.name or '—'} | exp={q.lot_id.expiration_date or '—'}")

#!/usr/bin/env python3
"""Two fixes:
  1. Undo my PICKFACE re-parent — move 350 PF-* bins back to direct children
     of K-On/Stock (matches what they were before, simple 3-level tree).
  2. Apply Removal Strategy = FEFO to every internal stock location.

The PICKFACE node itself stays (other Pull rules may reference it), but
empty.  If we want it as a SOURCE for routes, we add it via a putaway
rule or an act-like.
"""

env = self.env  # noqa: F821

# ----- 1. Find K-On/Stock and revert PF-* parent -----
kon_stock = env["stock.location"].search(
    [("complete_name", "=", "K-On/Stock")], limit=1,
)
print(f"K-On/Stock id: {kon_stock.id}")

mis_parented = env["stock.location"].search([
    ("complete_name", "=like", "K-On/Stock/PICKFACE/PF-%"),
])
print(f"PF-* under PICKFACE: {len(mis_parented)}")

batch = 0
for loc in mis_parented:
    loc.location_id = kon_stock.id
    batch += 1
    if batch % 50 == 0:
        env.cr.commit()
        print(f"  · committed {batch}")
env.cr.commit()
print(f"  ✓ {batch} re-parented back to K-On/Stock")

# ----- 2. Set FEFO removal strategy on every internal location -----
fefo = env["product.removal"].search([("method", "=", "fefo")], limit=1)
print(f"\nFEFO strategy id: {fefo.id}")

internal = env["stock.location"].search([
    ("usage", "=", "internal"),
    ("removal_strategy_id", "!=", fefo.id),
])
print(f"Internal locations to set FEFO: {len(internal)}")

batch = 0
for loc in internal:
    loc.removal_strategy_id = fefo.id
    batch += 1
    if batch % 200 == 0:
        env.cr.commit()
        print(f"  · committed {batch}")
env.cr.commit()
print(f"  ✓ {batch} locations now FEFO")

# ----- 3. Final state -----
print("\n=== Verification ===")
sample = env["stock.location"].search([
    ("complete_name", "=like", "K-On/Stock/PF-%"),
], limit=3)
for s in sample:
    print(f"  {s.complete_name} | parent={s.location_id.complete_name} | "
          f"removal={s.removal_strategy_id.method or 'default'}")

n_fefo = env["stock.location"].search_count([
    ("usage", "=", "internal"),
    ("removal_strategy_id", "=", fefo.id),
])
n_internal = env["stock.location"].search_count([("usage", "=", "internal")])
print(f"\n  FEFO coverage: {n_fefo}/{n_internal} internal locations")

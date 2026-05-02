#!/usr/bin/env python3
"""Re-parent all PF-A through PF-G locations under K-On/Stock/PICKFACE.

After this:
  - Pull rules with source=PICKFACE will source from any of the 350 sub-bins
  - Putaway rules can target PICKFACE and Odoo distributes to first available
  - Storage categories can be added later if needed for size/weight constraints
"""

env = self.env  # noqa: F821

pickface_kon = env["stock.location"].search(
    [("complete_name", "=", "K-On/Stock/PICKFACE")], limit=1,
)
print(f"PICKFACE parent: id={pickface_kon.id}")

# Find all K-On PF-* locations whose parent is NOT yet PICKFACE
to_reparent = env["stock.location"].search([
    ("complete_name", "=like", "K-On/Stock/PF-%"),
    ("location_id", "!=", pickface_kon.id),
])
print(f"Locations to re-parent: {len(to_reparent)}")

# Re-parent in batches
batch = 0
for loc in to_reparent:
    loc.location_id = pickface_kon.id
    batch += 1
    if batch % 50 == 0:
        env.cr.commit()
        print(f"  · committed {batch}")
env.cr.commit()
print(f"  ✓ {batch} re-parented")

# Verify
sample = env["stock.location"].search([
    ("complete_name", "=like", "K-On/Stock/PICKFACE/PF-%"),
], limit=5)
print(f"\nSample after re-parent:")
for s in sample:
    print(f"  {s.complete_name}")

# Apply same to BTV (B-On) and CMN (C-On) if they exist
for prefix, name in [("B-On", "BTV"), ("C-On", "CMN")]:
    pf_root = env["stock.location"].search(
        [("complete_name", "=", f"{prefix}/Stock/PICKFACE")], limit=1,
    )
    if not pf_root:
        print(f"\n  · {name}: no {prefix}/Stock/PICKFACE root (skipping)")
        continue
    bins = env["stock.location"].search([
        ("complete_name", "=like", f"{prefix}/Stock/PF-%"),
        ("location_id", "!=", pf_root.id),
    ])
    if bins:
        print(f"\n  → {name}: re-parenting {len(bins)} bins under PICKFACE")
        for b in bins:
            b.location_id = pf_root.id
        env.cr.commit()

# Final summary
print("\n=== Final structure ===")
for prefix in ["K-On", "B-On", "C-On"]:
    pf = env["stock.location"].search(
        [("complete_name", "=", f"{prefix}/Stock/PICKFACE")], limit=1,
    )
    if pf:
        children = env["stock.location"].search_count(
            [("location_id", "=", pf.id)],
        )
        print(f"  {prefix}/Stock/PICKFACE → {children} sub-bins")

#!/usr/bin/env python3
"""Enforce: every top-level app menu lands on its first sub-menu's action.

For each menu where parent_id IS NULL and web_icon IS NOT NULL:
  - Walk into first child by (sequence, id), keep going until we find a
    menu with action set
  - Copy that action to the top-level app menu

That makes "open app → first deep sub-menu" deterministic.
"""

env = self.env  # noqa: F821

apps = env["ir.ui.menu"].search([
    ("parent_id", "=", False),
    ("web_icon", "!=", False),
])
print(f"Top-level apps to audit: {len(apps)}")

def first_action_descendant(menu):
    """Walk down via first-by-sequence child until we find one with action."""
    cur = menu
    visited = set()
    depth = 0
    while cur:
        if cur.id in visited or depth > 8:
            return None
        visited.add(cur.id)
        depth += 1
        if cur.action:
            return cur
        children = env["ir.ui.menu"].search(
            [("parent_id", "=", cur.id)],
            order="sequence, id",
            limit=1,
        )
        if not children:
            return None
        cur = children
    return None

updated = 0
for app in apps:
    leaf = first_action_descendant(app)
    if not leaf:
        print(f"  · {app.name}: no leaf action found, skipping")
        continue
    if app.id == leaf.id:
        # app itself already has action
        print(f"  ✓ {app.name}: action already set ({app.action})")
        continue
    if app.action and app.action == leaf.action:
        print(f"  ✓ {app.name}: already points to first leaf")
        continue
    print(f"  → {app.name:25s}  set action ← {leaf.name} ({leaf.action})")
    # Direct write to action field — it's a Reference field
    app.action = leaf.action
    updated += 1

env.cr.commit()
print(f"\n✓ {updated} apps updated to land on first leaf sub-menu")

# Final report
print("\n=== Final landing actions ===")
for app in apps.sorted(lambda m: (m.sequence or 0, m.id)):
    leaf = first_action_descendant(app)
    leaf_name = leaf.name if leaf else "—"
    print(f"  {app.name:25s} → {leaf_name}")

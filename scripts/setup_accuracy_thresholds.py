env = self.env  # noqa: F821

# 1. Set accuracy_threshold on every cycle count rule
#    KOB cosmetics tolerance:
#    - High-velocity zones (PF-A,B,C 30-day): 95% accuracy required
#    - Mid-velocity (D,E 60-day): 92%
#    - Slow (F,G 90-day): 90%
RULE_THRESHOLDS = {
    "PF-A Periodic Count (30d)": 95.0,
    "PF-B Periodic Count (30d)": 95.0,
    "PF-C Periodic Count (30d)": 95.0,
    "PF-D Periodic Count (60d)": 92.0,
    "PF-E Periodic Count (60d)": 92.0,
    "PF-F Periodic Count (90d)": 90.0,
    "PF-G Periodic Count (90d)": 90.0,
}

print("Step 1: Set accuracy_threshold on rules")
for rule in env["stock.cycle.count.rule"].search([]):
    if rule.name in RULE_THRESHOLDS:
        rule.accuracy_threshold = RULE_THRESHOLDS[rule.name]
        print(f"  · {rule.name}: {rule.accuracy_threshold}%")

# 2. Set discrepancy_threshold on warehouses (5% default for cosmetics)
#    Cascades to all internal locations under each warehouse.
print("\nStep 2: Set discrepancy_threshold = 5% on all warehouses")
for wh in env["stock.warehouse"].search([]):
    wh.discrepancy_threshold = 5.0
    print(f"  · {wh.code}: 5%")

# Also set on key parent locations (PICKFACE) for finer control
print("\nStep 2b: Set discrepancy_threshold = 5% on PICKFACE parent locations")
for loc in env["stock.location"].search([
    ("complete_name", "ilike", "PICKFACE"),
]):
    loc.discrepancy_threshold = 5.0
    print(f"  · {loc.complete_name}: 5%")
env.cr.commit()

# 3. Re-tick the inventory_accuracy on existing inventories using the rule's threshold
print("\nStep 3: Recompute accuracy on existing inventories")
for inv in env["stock.inventory"].search([("state", "=", "done")]):
    try:
        if hasattr(inv, "_compute_inventory_accuracy"):
            inv._compute_inventory_accuracy()
    except Exception:
        pass

env.cr.commit()

# Final
print("\n=== Final ===")
for r in env["stock.cycle.count.rule"].search([], order="name"):
    print(f"  {r.name:30s} | accuracy_threshold = {r.accuracy_threshold}%")
print(f"\n  Warehouses with threshold > 0: "
      f"{env['stock.warehouse'].search_count([('discrepancy_threshold', '>', 0)])}")
print(f"  Locations with threshold > 0: "
      f"{env['stock.location'].search_count([('discrepancy_threshold', '>', 0)])}")

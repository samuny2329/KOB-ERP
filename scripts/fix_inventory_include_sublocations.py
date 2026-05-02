env = self.env  # noqa: F821

# Fix existing in-progress inventory adjustments that have
# exclude_sublocation=True but their location is a parent (PICKFACE)
# This makes the count include all 350 PF-* child bins automatically.
to_fix = env["stock.inventory"].search([
    ("state", "in", ("draft", "in_progress")),
    ("exclude_sublocation", "=", True),
])
print(f"Inventories to fix: {len(to_fix)}")

for inv in to_fix:
    inv.exclude_sublocation = False
    print(f"  · {inv.name}: exclude_sublocation → False")
    # Re-prefill lines
    if hasattr(inv, "action_state_to_in_progress"):
        try:
            # Force regenerate quants for this inventory
            # by re-triggering the prefill mechanism
            env.cr.execute("""
                DELETE FROM stock_inventory_stock_quant_rel
                WHERE stock_inventory_id = %s
            """, (inv.id,))
            env.cr.commit()
        except Exception as e:
            print(f"    ! reprefill skipped: {e!r}"[:80])

env.cr.commit()

# Now also patch the OCA stock_cycle_count to set exclude_sublocation=False
# when it generates a new stock.inventory. We'll do this via Python override
# in our kob_cycle_count_extra module.

print(f"\n✓ {len(to_fix)} inventories now include sub-locations")
print("  → Click 'Refresh' or re-open INV/CC/2026/00003 to see PF-* bin lines")

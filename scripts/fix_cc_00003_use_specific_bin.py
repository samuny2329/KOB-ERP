env = self.env  # noqa: F821

# Step 1: Cancel the broken INV/CC/2026/00003 (parent location, no descendants)
inv = env["stock.inventory"].search(
    [("name", "=", "INV/CC/2026/00003")], limit=1,
)
if inv:
    print(f"Cancelling INV/CC/2026/00003 (state={inv.state})")
    try:
        if hasattr(inv, "action_cancel"):
            inv.action_cancel()
        else:
            env.cr.execute(
                "UPDATE stock_inventory SET state = 'cancelled' WHERE id = %s",
                (inv.id,),
            )
            env.cr.commit()
    except Exception as e:
        print(f"  ! cancel failed: {e!r}"[:100])

# Step 2: Cancel the parent CC/2026/00003 cycle count
cc = env["stock.cycle.count"].search(
    [("name", "=", "CC/2026/00003")], limit=1,
)
if cc:
    print(f"Cancelling CC/2026/00003 (state={cc.state})")
    try:
        cc.do_cancel()
    except Exception as e:
        # Fallback: SQL update
        env.cr.execute(
            "UPDATE stock_cycle_count SET state = 'cancelled' WHERE id = %s",
            (cc.id,),
        )
        env.cr.commit()

# Step 3: Force-recompute (run cron manually) for new cycle counts
print("\nRunning cycle count cron to generate fresh CCs...")
try:
    cron = env.ref("stock_cycle_count.run_cycle_count_planner", raise_if_not_found=False)
    if cron:
        cron.method_direct_trigger()
        print("  ✓ cron triggered")
except Exception as e:
    print(f"  ! cron trigger: {e!r}"[:100])

env.cr.commit()

# Show new cycle counts that just got created
print("\n=== Cycle counts ===")
for c in env["stock.cycle.count"].search([], order="id DESC", limit=10):
    print(f"  {c.name} | {c.location_id.complete_name} | rule={c.cycle_count_rule_id.name} | state={c.state}")

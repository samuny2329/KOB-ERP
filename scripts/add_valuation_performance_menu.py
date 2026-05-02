env = self.env  # noqa: F821 — odoo shell

reporting_menu = env["ir.ui.menu"].search(
    [("name", "=", "Reporting"), ("parent_id", "=", 228)], limit=1,
)
print(f"Reporting menu id: {reporting_menu.id}")

# 1. Valuation — points to native stock_account stock_move_valuation_action (id 478)
val_act = env.ref("stock_account.stock_move_valuation_action", raise_if_not_found=False)
if val_act:
    existing = env["ir.ui.menu"].search([
        ("name", "=", "Valuation"),
        ("parent_id", "=", reporting_menu.id),
    ], limit=1)
    if not existing:
        env["ir.ui.menu"].create({
            "name": "Valuation",
            "parent_id": reporting_menu.id,
            "action": f"ir.actions.act_window,{val_act.id}",
            "sequence": 50,
        })
        print(f"  ✓ Valuation menu created → action {val_act.id}")
    else:
        print(f"  · Valuation menu already exists (id {existing.id})")

# 2. Performance — point to kob_wms.action_wms_worker_performance
perf_act = env.ref("kob_wms.action_wms_worker_performance", raise_if_not_found=False)
if perf_act:
    existing = env["ir.ui.menu"].search([
        ("name", "=", "Performance"),
        ("parent_id", "=", reporting_menu.id),
    ], limit=1)
    if not existing:
        env["ir.ui.menu"].create({
            "name": "Performance",
            "parent_id": reporting_menu.id,
            "action": f"ir.actions.act_window,{perf_act.id}",
            "sequence": 60,
        })
        print(f"  ✓ Performance menu created → action {perf_act.id}")
    else:
        print(f"  · Performance menu already exists (id {existing.id})")

env.cr.commit()

print("\n=== Inventory > Reporting menu ===")
for m in env["ir.ui.menu"].search(
    [("parent_id", "=", reporting_menu.id), ("active", "=", True)],
    order="sequence, id",
):
    print(f"  {m.sequence:3d} | {m.name} | {m.action}")

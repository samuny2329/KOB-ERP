"""Seed KPI Dashboard menu items pointing to existing pivot/graph views.

Approach: create act_window pointing to existing native actions but with
'view_mode': 'graph,pivot' as default + sensible context filters.

Top-level menu: KOB Dashboards
  ├─ Sales (SO pivot by partner/month)
  ├─ Purchase (PO pivot by vendor/month)
  ├─ Inventory (stock.move pivot)
  ├─ Manufacturing (MO pivot by workcenter)
  ├─ Helpdesk (ticket pivot)
  └─ Project Hours (timesheet pivot)
"""
env = self.env  # noqa: F821

# 1. Top-level menu under KOB ERP
parent = env.ref("kob_base.menu_kob_root", raise_if_not_found=False)
if not parent:
    print("kob_base.menu_kob_root missing — skipping")
else:
    dash_menu = env["ir.ui.menu"].search([
        ("name", "=", "📊 Dashboards"), ("parent_id", "=", parent.id),
    ], limit=1)
    if not dash_menu:
        dash_menu = env["ir.ui.menu"].create({
            "name": "📊 Dashboards",
            "parent_id": parent.id,
            "sequence": 5,
        })
        print(f"  ✓ Top menu: 📊 Dashboards (id={dash_menu.id})")

    # 2. Dashboard sub-items pointing to existing pivot/graph actions
    DASHBOARDS = [
        ("Sales — Revenue by Partner",
         "sale.order",
         "graph,pivot",
         {"search_default_state_sale": 1, "search_default_groupby_partner_id": 1}),
        ("Sales — Revenue by Month",
         "sale.order",
         "graph,pivot",
         {"search_default_state_sale": 1}),
        ("Purchase — Spend by Vendor",
         "purchase.order",
         "graph,pivot",
         {"search_default_partner_id": 1}),
        ("Purchase — Spend by Month",
         "purchase.order",
         "graph,pivot",
         {}),
        ("Inventory — Moves Analysis",
         "stock.move",
         "graph,pivot",
         {"search_default_done": 1}),
        ("Manufacturing — MO by Workcenter",
         "mrp.production",
         "graph,pivot",
         {}),
        ("Helpdesk — Open Tickets",
         "kob.helpdesk.ticket",
         "graph,pivot",
         {"search_default_open": 1}),
        ("Worker Performance — KPI",
         "wms.worker.performance",
         "graph,pivot",
         {}),
        ("Cycle Count Accuracy",
         "stock.inventory",
         "graph,pivot",
         {}),
        ("Customer LTV — Top Customers",
         "kob.customer.ltv.snapshot",
         "graph,pivot",
         {}),
        ("Vendor Performance — Score",
         "kob.vendor.performance",
         "graph,pivot",
         {}),
        ("Product Margins — Channel",
         "kob.channel.margin",
         "graph,pivot",
         {}),
    ]

    seq = 10
    for label, model, view_mode, ctx in DASHBOARDS:
        if not env["ir.model"].search([("model", "=", model)], limit=1):
            continue
        action = env["ir.actions.act_window"].create({
            "name": f"📊 {label}",
            "res_model": model,
            "view_mode": view_mode,
            "context": str(ctx),
        })
        env["ir.ui.menu"].create({
            "name": label,
            "parent_id": dash_menu.id,
            "sequence": seq,
            "action": f"ir.actions.act_window,{action.id}",
        })
        seq += 10
        print(f"  ✓ Dashboard: {label} → {model}")

env.cr.commit()

print("\n=== Final ===")
n = env["ir.ui.menu"].search_count(
    [("parent_id", "=", dash_menu.id), ("active", "=", True)],
)
print(f"  📊 Dashboards menu items: {n}")

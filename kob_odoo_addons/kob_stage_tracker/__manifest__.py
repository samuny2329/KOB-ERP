# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Auto Stage-Time Tracker",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Productivity",
    "summary": "Auto-records timestamp on every stage transition. "
               "Alerts when stage stays past threshold. Drill-back to upstream.",
    "description": """
KOB ERP — Auto Stage-Time Tracker
=================================
Generic AbstractModel mixin that any model with a state field can inherit.

Auto-captures every state transition into kob.stage.transition with:
- res_model, res_id (polymorphic)
- stage_from, stage_to, transitioned_at, transitioned_by
- duration_in_previous_min (working-hours aware via wms.sla.config)

Plus:
- kob.stage.threshold — configurable per (model, state) thresholds
- Cron every 15 min — scan breached records, dispatch alerts
- 4 alert actions: mail.activity / Battle Board / Discuss / AI agent
- Upstream chain walker (stock.picking → PO → approval request)

Pre-applied to: purchase.order (approval_state), stock.picking (state),
kob.approval.step (state).
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "purchase",
        "stock",
        "kob_purchase_pro",
        "kob_extras_v2",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cron.xml",
        "data/thresholds.xml",
        "views/stage_transition_views.xml",
        "views/stage_threshold_views.xml",
        "views/purchase_order_views.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}

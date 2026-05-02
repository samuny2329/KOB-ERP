# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Sales Pro",
    "version": "19.0.1.1.0",
    "category": "KOB ERP/Sales",
    "summary": "RMA returns, multi-platform order linkage, channel margin, "
               "customer LTV snapshots, intercompany SO mirror.",
    "description": """
KOB ERP — Sales Pro
===================
Phase 4-adv port — KOB-exclusive on top of Odoo's stock ``sale``:

* **ReturnOrder (RMA)** — header + lines + state machine (draft →
  received → restocked / scrapped) with structured reason codes.
* **MultiPlatformOrder** — one Odoo SO can be filled from many
  Shopee/Lazada/TikTok platform orders, each with its own commission.
* **ChannelMargin** — refreshable margin view per channel after fees,
  shipping, returns.
* **CustomerLtvSnapshot** — append-only 90-day spend / repeat /
  return rate scoreboard.
* **IntercompanyTransfer** — when company A's SO ships from
  company B's warehouse, auto-create the mirror PO on B side.
""",
    "author": "Kiss of Beauty (KOB)",
    "website": "https://kissofbeauty.co.th",
    "license": "LGPL-3",
    "depends": [
        "kob_base",
        "sale_management",
        "stock",
        "account",
        "purchase",
        "mail",
        "kob_marketplace_import",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/menu.xml",
        "views/return_order_views.xml",
        "views/multi_platform_order_views.xml",
        "views/channel_margin_views.xml",
        "views/ltv_snapshot_views.xml",
        "views/intercompany_transfer_views.xml",
        # QWeb PDF reports
        "report/sales_pro_reports.xml",
    ],
    "installable": True,
    "auto_install": False,
}

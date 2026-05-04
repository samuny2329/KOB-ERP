# -*- coding: utf-8 -*-
{
    "name": "KOB Daily Report — Dispatch (MS Teams)",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Reports",
    "summary": (
        "End-of-day Outbound/Dispatch summary card sent to Microsoft "
        "Teams via incoming webhook. Per-round / per-platform / per-courier."
    ),
    "description": """
KOB Daily Report — Dispatch
===========================
Adds a focused end-of-day dispatch summary that posts an Adaptive Card
to a Microsoft Teams channel via a configured incoming webhook.

* New model `wms.dispatch.daily.report` — one record per (company, day).
* Aggregates from `wms.dispatch.round`, `wms.courier.batch`, and
  `wms.scan.item` (kob_wms + kob_wms_auto_batch).
* Cron 18:00 daily → compute metrics + POST to Teams webhook.
* Minimal Enterprise-style card mirroring kob_account_reports look.
* Falls back to Discuss inbox post if no webhook configured.
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "kob_wms",
        "kob_wms_auto_batch",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/multi_company_rules.xml",
        "data/cron.xml",
        "views/res_config_settings_views.xml",
        "views/dispatch_daily_report_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_daily_report_extras/static/src/dispatch_card.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
}

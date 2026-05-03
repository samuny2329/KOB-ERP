# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Webhooks",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Tools",
    "summary": "Outgoing webhook config + delivery log for external integrations",
    "depends": ["base", "sale", "account", "stock", "kob_helpdesk"],
    "data": [
        "security/ir.model.access.csv",
        "views/webhook_views.xml",
        "data/seed_data.xml",
    ],
    "installable": True,
    "auto_install": False,
}

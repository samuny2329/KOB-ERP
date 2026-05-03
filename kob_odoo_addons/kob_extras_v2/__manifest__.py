# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Extras v2 (Phases 29-34)",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Extras",
    "summary": (
        "Approval workflow engine + Multi-channel notifications + "
        "Field service tasks + ESG metrics + AI suggestions + "
        "Multi-warehouse rebalancing proposals."
    ),
    "depends": ["base", "mail", "stock", "account", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/kob_extras_views.xml",
        "data/seed_data.xml",
    ],
    "installable": True,
    "auto_install": False,
}

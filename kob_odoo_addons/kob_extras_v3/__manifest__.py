# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Extras v3 (Phases 35-40)",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Extras",
    "summary": (
        "Bulk import wizard + ภงด.91 report + Cron dashboard + "
        "RBAC audit + Mobile CSS + Onboarding wizard."
    ),
    "depends": [
        "base", "mail",
        "kob_thai_compliance",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/bulk_import_views.xml",
        "wizards/onboarding_wizard_views.xml",
        "views/cron_dashboard_views.xml",
        "report/pnd91_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_extras_v3/static/src/mobile_tweaks.css",
        ],
    },
    "installable": True,
    "auto_install": False,
}

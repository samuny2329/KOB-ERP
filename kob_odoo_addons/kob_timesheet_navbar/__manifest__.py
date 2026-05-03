# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Timesheet Timer (navbar)",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Productivity",
    "summary": "One-click time tracking from anywhere in Odoo. Backport of "
               "Odoo 20's Timesheet Timer header bar feature.",
    "description": """
KOB ERP — Timesheet Timer in navbar
====================================
Click once anywhere in Odoo to start tracking time. Display elapsed
time live in the top navbar. Stop creates an account.analytic.line
(if hr_timesheet installed) or a lightweight kob.timer.entry.

Inspired by Odoo 20's native Timesheet Timer feature, available now
on Odoo 19.
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["web", "hr_timesheet"],
    "data": [
        "security/ir.model.access.csv",
        "views/timer_entry_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_timesheet_navbar/static/src/timer_button.js",
            "kob_timesheet_navbar/static/src/timer_button.xml",
            "kob_timesheet_navbar/static/src/timer_button.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
}

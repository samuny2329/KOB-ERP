# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Datetime Full Format",
    "version": "19.0.1.0.1",
    "category": "KOB ERP/Tools",
    "summary": "Force all datetime fields to render as DD/MM/YYYY HH:MM:SS",
    "description": """
KOB ERP — Datetime Full Format
==============================
Patches the Odoo 19 frontend `formatDateTime` so it ALWAYS renders the
full lang format (date_format + time_format) for every datetime field.

Without this patch, Odoo defaults to Luxon's `DATETIME_SHORT` preset
which uses the browser locale (e.g. "May 2, 4:41 PM" for en-US),
ignoring our lang's 24-hour `%H:%M:%S` setting.

Result: every datetime everywhere → "02/05/2026 18:52:53"
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "post_init_hook": "_post_init_hook",
    "assets": {
        "web.assets_backend": [
            "kob_datetime_full_format/static/src/datetime_format_patch.js",
        ],
    },
    "installable": True,
    "auto_install": True,
}

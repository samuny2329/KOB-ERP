# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Theme",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Foundation",
    "summary": "SAP Fiori-style web theme for the Odoo 19 web client.",
    "description": """
KOB ERP — Theme
===============
Re-skins Odoo 19's web client with a SAP Fiori-inspired palette + shellbar
treatment.  Brand colour is Fiori action blue (#0a6ed1) on white surfaces;
the navbar adopts the Belize Hole navy (#354A5F) used by Fiori shellbars.

Loaded after the standard ``web`` bundle so our SCSS overrides win.  No
existing Odoo SCSS files are modified — we override at the variable level
through Odoo's primary_variables hook.
""",
    "author": "Kiss of Beauty (KOB)",
    "website": "https://kissofbeauty.co.th",
    "license": "LGPL-3",
    "depends": ["web", "kob_base"],
    "assets": {
        # Load BEFORE Odoo's primary/secondary variables.scss so our
        # non-default assignments are seen first; Odoo's `!default` then
        # no-ops, and every downstream `darken(...)` / `mix(...)` uses our
        # palette instead of the original Odoo purple.
        "web._assets_primary_variables": [
            ("before", "web/static/src/scss/primary_variables.scss",
             "kob_theme/static/src/scss/primary_variables.scss"),
        ],
        "web._assets_secondary_variables": [
            ("before", "web/static/src/scss/secondary_variables.scss",
             "kob_theme/static/src/scss/secondary_variables.scss"),
        ],
        "web.assets_backend": [
            "kob_theme/static/src/scss/webclient.scss",
        ],
        "web.assets_frontend": [
            "kob_theme/static/src/scss/frontend.scss",
        ],
    },
    "data": [],
    "installable": True,
    "auto_install": False,
}

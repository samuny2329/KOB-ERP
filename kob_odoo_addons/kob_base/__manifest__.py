# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Base",
    "version": "19.0.1.0.3",
    "category": "KOB ERP/Foundation",
    "summary": "KOB ERP foundation: branding, system params, dependency hub.",
    "description": """
KOB ERP — Base
==============
Foundation addon for the KOB ERP distribution.

Loaded first by every other ``kob_*`` addon.  Owns:

* Branding strings: company tagline, login screen header.
* Catalog of system parameters used across the KOB suite.
* Menu group ``KOB ERP`` (parent menu shared by every kob_* feature module).
""",
    "author": "Kiss of Beauty (KOB)",
    "website": "https://kissofbeauty.co.th",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "data/system_params.xml",
        "data/welcome_action.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_base/static/src/welcome/kob_welcome.js",
            "kob_base/static/src/welcome/kob_welcome.xml",
            "kob_base/static/src/welcome/kob_welcome.scss",
            "kob_base/static/src/navbar_brand/kob_brand.js",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}

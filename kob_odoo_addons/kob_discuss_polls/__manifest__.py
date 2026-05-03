# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Polls in Discuss",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Discuss",
    "summary": "Create timed voting polls inside Odoo Discuss channels.",
    "description": """
KOB ERP — Polls in Discuss
==========================
Backport of Odoo 20's "Polls in Discuss" feature.

Use the **/poll** slash command in any Discuss channel to spin up a
quick vote without leaving Odoo.

Example: ``/poll Lunch tomorrow? Pizza, Sushi, Salad``
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/poll_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_discuss_polls/static/src/poll_message.js",
            "kob_discuss_polls/static/src/poll_message.xml",
            "kob_discuss_polls/static/src/poll_message.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
}

# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Activity in Calendar",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Discuss",
    "summary": "Reschedule + complete activities directly in calendar view.",
    "description": """
KOB ERP — Activity Calendar Enhancements
=========================================
Backport of Odoo 20's Activity Management in Calendar feature.

Adds a calendar view to mail.activity that supports:
- Drag-to-reschedule (changes ``date_deadline`` on drop)
- One-click "Mark done" overlay button on each event
- Color by activity_type_id

Available everywhere mail.activity exists (CRM, Sales, Purchase, ...).
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["mail"],
    "data": [
        "views/activity_calendar_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}

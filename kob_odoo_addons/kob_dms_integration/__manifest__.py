# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — DMS Integration",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Tools",
    "summary": "Attach DMS folder + Documents smart button on every key record",
    "description": """
KOB ERP — DMS Integration
==========================
Adds a "Documents" smart button on:
  - purchase.order      → KOB Documents/Vendors/<PO Reference>
  - sale.order          → KOB Documents/Customers/<SO Reference>
  - hr.employee         → KOB Documents/Employees/<Employee Name>
  - kob.fixed.asset     → KOB Documents/Assets/<Asset Code>
  - account.move        → KOB Documents/<Vendors|Customers>/<Move Number>

Each click:
  1. Auto-creates a per-record sub-directory inside the parent KOB folder
  2. Opens a filtered file list scoped to that directory
  3. file_count smart-displays total docs for the record
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["dms", "purchase", "sale", "hr", "account", "kob_thai_compliance"],
    "data": [
        "views/dms_integration_views.xml",
    ],
    "installable": True,
    "auto_install": True,
}

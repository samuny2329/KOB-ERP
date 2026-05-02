# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Cycle Count Auto-Location",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Inventory",
    "summary": "Auto-populate Location on Stock Cycle Count when rule is chosen",
    "description": """
KOB ERP — Cycle Count Auto-Location
====================================
Adds @api.onchange('cycle_count_rule_id') on stock.cycle.count.
When user selects a Cycle Count Rule, Location is auto-filled with the
deepest common ancestor of all the rule's linked locations.

Example: rule "PF-A Periodic Count (30d)" links to 50 bins all under
K-On/Stock/PICKFACE → Location auto-set to K-On/Stock/PICKFACE.
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["stock_cycle_count"],
    "data": [],
    "installable": True,
    "auto_install": True,
}

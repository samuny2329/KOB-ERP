# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Manufacturing Pro",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Manufacturing",
    "summary": "Work-center OEE, production shifts, MO production signal, "
               "batch consolidation, BOM versioning.",
    "description": """
KOB ERP — Manufacturing Pro
===========================
Phase 8-adv port — KOB-exclusive layer on Odoo ``mrp``:

* **WorkCenterOee** — per-shift OEE (availability × performance ×
  quality) with rolling KPI feed.
* **ProductionShift** — explicit shift model (morning/afternoon/
  night) tying employees, MOs, and OEE entries together.
* **MoProductionSignal** — append-only signal from sales velocity +
  stock levels that proposes new MOs.
* **BatchConsolidation** — aggregate small MOs into one larger
  batch when same-product / same-window.
* **BomVersion** — versioned BOMs with effective-date ranges.
""",
    "author": "Kiss of Beauty (KOB)",
    "website": "https://kissofbeauty.co.th",
    "license": "LGPL-3",
    "depends": [
        "kob_base",
        "mrp",
        "stock",
        "hr",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/menu.xml",
        "views/production_shift_views.xml",
        "views/work_center_oee_views.xml",
        "views/production_signal_views.xml",
        "views/batch_consolidation_views.xml",
        "views/bom_version_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}

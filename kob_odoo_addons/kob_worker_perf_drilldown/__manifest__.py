# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Worker Performance Drill-down",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Inventory",
    "summary": "Form view + Activity Log drill-down on Worker Performance",
    "description": """
KOB ERP — Worker Performance Drill-down
========================================
Click a row in Inventory > Reporting > Performance and dive into:
  - Full KPI breakdown (Picks/Packs/Ships, Errors, UPH, Quality, Score)
  - Smart button to wms.activity.log filtered by (kob_user_id, date)
  - Smart button to wms.sales.order completed that day
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["kob_wms"],
    "data": [
        "views/wms_worker_performance_form.xml",
    ],
    "installable": True,
    "auto_install": True,
}

# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Purchase Pro",
    "version": "19.0.1.1.0",
    "category": "KOB ERP/Purchase",
    "summary": "Vendor performance scoring, procurement budget gating, "
               "demand signal, PO consolidation, Thai WHT integration.",
    "description": """
KOB ERP — Purchase Pro
======================
Phase 3-adv port: Odoo 19 parity + KOB-exclusive features that go
beyond what stock Odoo ships:

* **VendorPerformance** — rolling on-time / quality / price-stability
  score per vendor, refreshable from completed POs.
* **ProcurementBudget** — annual / quarterly budget pots that
  auto-validate POs against remaining budget before approval.
* **DemandSignal** — append-only feed from sales velocity / stock
  levels driving auto-RFQ creation.
* **PoConsolidation** — combine POs across companies in the group
  to qualify for vendor volume tiers.
* **WHT integration** — auto-create ``kob.wht.certificate`` on
  payment when the vendor is a withholding-tax target.
""",
    "author": "Kiss of Beauty (KOB)",
    "website": "https://kissofbeauty.co.th",
    "license": "LGPL-3",
    "depends": [
        "kob_base",
        "purchase",
        "account",
        "kob_thai_compliance",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/menu.xml",
        "views/vendor_performance_views.xml",
        "views/procurement_budget_views.xml",
        "views/demand_signal_views.xml",
        "views/po_consolidation_views.xml",
        # QWeb PDF reports
        "report/purchase_pro_reports.xml",
    ],
    "installable": True,
    "auto_install": False,
}

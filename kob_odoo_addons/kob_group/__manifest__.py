# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Group / Multi-Company",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Group",
    "summary": "Inventory pooling, cost allocation, intercompany loan, "
               "approval matrix, cash pool, transfer pricing, volume rebate.",
    "description": """
KOB ERP — Group
===============
Phase 11–13 port: the multi-company glue layer that ties บริษัท
คิสออฟบิวตี้ จำกัด, บริษัท บิวตี้วิลล์ จำกัด, and บริษัท
คอสโมเนชั่น จำกัด together as a Kiss-of-Beauty group.

Sub-areas:

* **Inventory pooling** — one virtual stock pool across companies
  with allocation rules.
* **Finance** — IntercompanyLoan, CashPool, GroupAccrual.
* **Governance** — ApprovalMatrix (cross-co spend gating),
  TransferPricing (intercompany invoice price rules).
* **Commercial** — BrandLicense, VolumeRebate (group-level
  vendor / customer rebates).
* **Partners** — CrossCompanyCustomer / CrossCompanyVendor mirroring.
""",
    "author": "Kiss of Beauty (KOB)",
    "website": "https://kissofbeauty.co.th",
    "license": "LGPL-3",
    "depends": [
        "kob_base",
        "account",
        "purchase",
        "sale_management",
        "stock",
        "kob_thai_compliance",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/menu.xml",
        "views/inventory_pool_views.xml",
        "views/approval_matrix_views.xml",
        "views/cost_allocation_views.xml",
        "views/intercompany_loan_views.xml",
        "views/cash_pool_views.xml",
        "views/volume_rebate_views.xml",
        # Group v2 — extra models
        "views/group_v2_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}

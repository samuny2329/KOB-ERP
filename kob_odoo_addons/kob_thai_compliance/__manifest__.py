# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Thailand Compliance",
    "version": "19.0.1.1.0",
    "category": "KOB ERP/Localization",
    "summary": "SSO, PND withholding tax, OT (Thai LPA), leave entitlement, "
               "fixed asset depreciation, FX revaluation — Thai SME compliance.",
    "description": """
KOB ERP — Thailand Compliance
=============================
Port of Phase 14 of the standalone KOB ERP into Odoo 19 addons.

Adds Thai-specific HR + Accounting compliance on top of stock Odoo:

* **SSO** — Article 33/39/40 registration, monthly contribution at 5%
  capped 750 THB.
* **PND withholding tax** — progressive bracket calculator + monthly
  filing record (PND1 / PND1A / PND2 / PND3 / PND53).
* **Overtime (LPA)** — weekday/weekend/holiday multipliers stored on the
  record so historic entries stay correct after rate changes.
* **Annual leave entitlement** — KOB tier above the LPA minimum
  (6/8/10/14 days by years of service).
* **Fixed asset** — straight-line / declining-balance depreciation.
* **FX revaluation** — period-end gain/loss on monetary balances.

Pure Thai-compliance functions live in ``models/services.py`` and have
no Odoo dependency, so unit-tested behaviour from Phase 14 carries over
verbatim.
""",
    "author": "Kiss of Beauty (KOB)",
    "website": "https://kissofbeauty.co.th",
    "license": "LGPL-3",
    "depends": ["kob_base", "hr", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/sso_views.xml",
        "views/pnd_views.xml",
        "views/overtime_views.xml",
        # Phase 5-adv — Thai accounting compliance
        "views/wht_certificate_views.xml",
        "views/vat_period_views.xml",
        "views/fixed_asset_views.xml",
        "views/fx_revaluation_views.xml",
        # Phase 6-adv — HR cross-company
        "views/employee_transfer_views.xml",
        # QWeb PDF reports — Thai compliance + Asset management
        "report/wht_certificate_report.xml",
        "report/asset_reports.xml",
        # Cron jobs (monthly depreciation posting)
        "data/asset_cron.xml",
    ],
    "installable": True,
    "auto_install": False,
}

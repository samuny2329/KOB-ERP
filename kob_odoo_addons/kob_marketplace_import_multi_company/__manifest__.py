# -*- coding: utf-8 -*-
{
    "name": "KOB Marketplace Import — Multi-Company Routing",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Sales",
    "summary": (
        "Validate product company on marketplace import. Auto-route SO "
        "to the company that actually stocks the product, raise warning "
        "for products not present in any allowed company."
    ),
    "description": """
KOB Marketplace Import — Multi-Company Routing
==============================================
Extends `kob.marketplace.import.wizard` so that on import:

* Each order line's product is resolved to a "home company" — the
  company whose warehouses have on-hand stock for that SKU. If
  multiple companies have stock, the wizard's primary company wins
  when present, otherwise the company with the highest qty wins.
* If a product has no stock anywhere → line is skipped with a
  warning ("ขึ้นฟ้อง" in the import log).
* If a product's home company differs from the wizard's primary
  company → the order is split: one SO per (home company) group.
  The wizard log clearly shows which company each SO landed in.
* New checkbox on the wizard "Enforce product company" (default ON)
  toggles the new behaviour off for legacy single-company imports.
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": [
        "kob_marketplace_import",
        "stock",
    ],
    "data": [
        "views/marketplace_import_wizard_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}

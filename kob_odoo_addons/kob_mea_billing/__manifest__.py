# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — MEA Billing Calculator",
    "version": "19.0.1.4.0",
    "category": "KOB ERP/Utilities",
    "summary": "Metropolitan Electricity Authority (MEA) bill calculator + analytics + Ft graph.",
    "description": """
KOB ERP — MEA Billing
=====================
Standalone calculator + analytics for Thai MEA electricity bills.

Phase 1 features:
* Meter registry (CA Number, Meter ID, site, tariff)
* Monthly bill history (kWh, energy, Ft, VAT, total)
* Cost calculator engine (TOU 3.2.3 + flat 2.1.2)
* Ft (Fuel Tariff) period table + lookup
* PDF extractor for SIGN_*.pdf (manual upload)
* Dashboard with KPI cards + Chart.js (Ft history line + 12-month bar)
* Custom SCSS polish (cards, table stripes, anomaly badges)

Standalone — does not link to or modify ``account.move``. AP flow untouched.
""",
    "author": "Kiss of Beauty (KOB)",
    "website": "https://kissofbeauty.co.th",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web", "kob_base"],
    # Optional: pdfplumber gives better table extraction for SIGN_*.pdf MEA bills.
    # Falls back to PyPDF2 (bundled with Odoo) when pdfplumber is unavailable —
    # accuracy may drop slightly without it. Install via:
    #     docker exec kob-odoo-19 pip install pdfplumber
    # We do NOT declare it in external_dependencies so install does not block.
    "data": [
        "security/mea_security.xml",
        "security/ir.model.access.csv",
        "data/mea_tariff_seed_data.xml",
        "data/mea_ft_seed_data.xml",
        "data/mea_meter_seed_data.xml",
        "data/mea_asset_category_data.xml",
        "data/mea_asset_seed_data.xml",
        "views/mea_tariff_views.xml",
        "views/mea_ft_period_views.xml",
        "views/mea_meter_views.xml",
        "views/mea_bill_history_views.xml",
        "views/mea_asset_views.xml",
        "wizards/mea_calculator_wizard_views.xml",
        "wizards/mea_pdf_import_wizard_views.xml",
        "views/mea_dashboard_views.xml",
        "views/mea_menus.xml",
        "wizards/import_throughput_wizard_views.xml",
        "wizards/import_ot_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_mea_billing/static/src/scss/mea_dashboard.scss",
            "kob_mea_billing/static/src/scss/mea_card.scss",
            "kob_mea_billing/static/src/js/mea_kpi_card.js",
            "kob_mea_billing/static/src/js/mea_ft_chart.js",
            "kob_mea_billing/static/src/js/mea_usage_chart.js",
            "kob_mea_billing/static/src/js/mea_dashboard.js",
            "kob_mea_billing/static/src/js/mea_meter_dashboard.js",
            "kob_mea_billing/static/src/xml/mea_dashboard.xml",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}

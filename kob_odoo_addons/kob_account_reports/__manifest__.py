{
    "name": "KOB Account Reports — Enterprise-style minimal tables",
    "version": "19.0.1.0.0",
    "summary": ("Profit and Loss, Balance Sheet, Journal Audit, Cash Flow, "
                "Executive Summary — minimal Odoo Enterprise-style report "
                "tables with PDF/XLSX exports and expand-collapse rows."),
    "author": "KOB Engineering",
    "license": "LGPL-3",
    "depends": ["base", "web", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/actions.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_account_reports/static/src/account_report.js",
            "kob_account_reports/static/src/account_report.xml",
            "kob_account_reports/static/src/account_report.scss",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}

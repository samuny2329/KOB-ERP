# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Predictive Financial Forecasting",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Accounting",
    "summary": "Forecast next-period revenue/expense from budget + actuals "
               "+ velocity. Backport of Odoo 20's native financial forecasting.",
    "description": """
KOB ERP — Predictive Financial Forecasting
==========================================
Generates monthly/quarterly forecasts using:

* Year-to-date actuals from account.move.line
* Configured budget targets per account / period
* Recent velocity (3-month moving average)
* Optional seasonality adjustment from prior 12 months

Output: ``kob.finance.forecast`` records with monthly buckets,
variance vs. budget, and projected end-of-year totals. Refreshable
via cron or manual "Refresh Forecast" button.
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/forecast_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}

# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Sales Stock Lite",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Sales",
    "summary": "View product stock + quick deliver from Sales without "
               "opening the full Inventory app.",
    "description": """
KOB ERP — Sales Stock Lite
==========================
Backport of Odoo 20's "Stock Tracking without Inventory" feature.

On every Sales Quotation/Order:
- New smart button **Stock** showing total available qty across all
  internal locations
- Click → list of stock.quants for products on the SO (live, filtered)
- "Quick Deliver" action creates a stock.picking (out type) on the
  fly, without leaving the Sales module

Useful for sales teams who don't need the full Inventory dashboard
but want immediate stock visibility on the SO they're quoting.
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": ["sale", "stock"],
    "data": [
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}

# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Marketplace Import",
    "version": "19.0.2.5.0",
    "category": "KOB ERP/Marketplace",
    "summary": "Import Shopee / TikTok / Lazada orders into Odoo as Sale "
               "Orders + Delivery Orders, with the x_kob_* custom fields "
               "the Print_Label-App pipeline expects.",
    "description": """
KOB ERP — Marketplace Import
============================
Adds:
* x_kob_* custom fields on stock.picking, stock.move, sale.order.line,
  product.template — required by KOB's Print_Label-App pipeline
* res.partner records: ECOMMERCE : SHOPEE / TIKTOK / LAZADA
* utm.source seed for known shop names (Shopee_KissMyBody, …)
* crm.tag "fake_order" for test/sample orders
* Wizard: Import Marketplace Orders — accepts Excel/CSV, picks platform
  + warehouse + company, creates SO → confirms → DO with x_kob_* fields
""",
    "author": "Kiss of Beauty (KOB)",
    "website": "https://kissofbeauty.co.th",
    "license": "LGPL-3",
    "depends": [
        "kob_base",
        "sale_management",
        "stock",
        "account",
        "utm",
        "crm",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/res_partner.xml",
        "data/utm_source.xml",
        "data/crm_tag.xml",
        "data/product_tag.xml",
        "data/sale_order_type.xml",
        "views/product_template_views.xml",
        "views/stock_picking_views.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/filter_views.xml",
        "wizards/marketplace_import_wizard_views.xml",
        # QWeb PDF reports (Tax Invoice / Proforma / Credit Note / Commercial Invoice / Journal Voucher)
        "report/account_move_reports.xml",
    ],
    "installable": True,
    "auto_install": False,
}

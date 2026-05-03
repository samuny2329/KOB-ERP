# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — Mini Helpdesk",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Services",
    "summary": "Lightweight ticket system — customer support, RMA inquiries",
    "depends": ["mail", "base", "account", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/kob_helpdesk_views.xml",
        "data/seed_data.xml",
    ],
    "installable": True,
    "auto_install": False,
}

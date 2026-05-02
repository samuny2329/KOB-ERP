# -*- coding: utf-8 -*-
{
    "name": "KOB ERP — KPI Tile Dashboard",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Tools",
    "summary": "Live KPI tiles aggregating sales/purchase/inventory/AR/AP",
    "depends": ["base", "account", "sale", "purchase", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/kpi_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}

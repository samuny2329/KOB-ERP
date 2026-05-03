{
    "name": "KOB ERP — Document Required on Receipt/Delivery/PO",
    "version": "19.0.1.0.0",
    "summary": ("Require photo or file attachment on stock.picking and "
                "purchase.order before validation."),
    "category": "Inventory",
    "author": "KOB Engineering",
    "license": "LGPL-3",
    "depends": ["base", "stock", "purchase"],
    "data": [
        "views/picking_views.xml",
        "views/purchase_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}

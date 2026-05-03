{
    "name": "KOB WMS — Unified User (PIN on res.users)",
    "version": "19.0.1.0.0",
    "summary": ("All Odoo users get WMS access. PIN is set directly on "
                "res.users; role inferred from Odoo security groups. "
                "Eliminates the separate kob.wms.user record per worker."),
    "category": "Inventory",
    "author": "KOB Engineering",
    "license": "LGPL-3",
    "depends": ["base", "web", "kob_wms"],
    "data": [
        "views/res_users_views.xml",
        "data/grant_wms_to_all_users.xml",
    ],
    "installable": True,
    "auto_install": False,
}

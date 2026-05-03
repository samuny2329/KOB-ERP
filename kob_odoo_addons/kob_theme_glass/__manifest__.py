{
    "name": "KOB ERP — Glass Theme (Transparent)",
    "version": "19.0.1.0.0",
    "summary": ("Global semi-transparent / glassmorphism theme overlay "
                "for Odoo 19 — applies to all list/form/kanban views, "
                "navbar, control panel."),
    "category": "Theme",
    "author": "KOB Engineering",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "kob_theme_glass/static/src/glass.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
}

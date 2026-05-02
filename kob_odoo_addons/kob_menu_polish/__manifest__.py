{
    "name": "KOB ERP — Menu Polish & Welcome Redesign",
    "version": "19.0.1.0.0",
    "summary": "Consolidate duplicate menus, sort sub-menus, redesign Welcome page",
    "author": "KOB Engineering",
    "license": "LGPL-3",
    "depends": [
        "base", "web", "mail",
        "kob_base", "kob_group",
        "kob_kpi_tiles", "kob_helpdesk", "kob_webhooks", "kob_backup",
        "kob_extras_v2", "kob_extras_v3", "kob_extras_v4",
    ],
    "data": [
        "views/menu_consolidation.xml",
        "views/welcome_homepage.xml",
        "views/kob_tools_app.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_menu_polish/static/src/welcome.css",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}

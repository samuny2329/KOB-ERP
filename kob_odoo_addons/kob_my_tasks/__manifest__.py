{
    "name": "🔥 My Battle Board — Personal task inbox",
    "version": "19.0.1.0.0",
    "summary": ("Aggregates pending tasks across modules into a single "
                "role-aware personal inbox per user."),
    "category": "Productivity",
    "author": "KOB Engineering",
    "license": "LGPL-3",
    "depends": [
        "base", "web", "mail",
        "kob_helpdesk", "kob_extras_v2", "kob_extras_v4",
        "kob_logistics_marketing", "kob_wms",
        "kob_group",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/role_source_map.xml",
        "data/cron_rules.xml",
        "data/views.xml",
        "data/client_action.xml",
        "data/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_my_tasks/static/src/my_battle_board.js",
            "kob_my_tasks/static/src/my_battle_board.xml",
            "kob_my_tasks/static/src/my_battle_board.scss",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}

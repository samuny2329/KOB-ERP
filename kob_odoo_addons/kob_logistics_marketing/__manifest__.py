{
    "name": "KOB ERP — Logistics & Marketing (Phases 48-54)",
    "version": "19.0.1.0.0",
    "summary": ("Multi-carrier shipping rate shop, label printing & tracking, "
                "returns workflow, email/SMS campaigns, coupon engine, "
                "attribution dashboard"),
    "author": "KOB Engineering",
    "license": "LGPL-3",
    "depends": [
        "base", "mail", "sale_management", "purchase",
        "stock", "delivery", "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/sequences.xml",
        "data/cron.xml",
        "data/seed_carriers.xml",
        "views/carrier_views.xml",
        "views/shipment_views.xml",
        "views/return_request_views.xml",
        "views/email_campaign_views.xml",
        "views/sms_views.xml",
        "views/coupon_views.xml",
        "views/attribution_views.xml",
        "views/menus.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}

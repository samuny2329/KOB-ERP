{
    "name": "Thiti Planning",
    "version": "19.0.0.1.0",
    "category": "Manufacturing/Planning",
    "summary": "Advanced Production Planning & Scheduling (powered by frePPLe engine)",
    "description": """
Thiti Planning
==============

Advanced Planning & Scheduling (APS) for KOB ERP.

Engine: frePPLe Community Edition (MIT) — embedded as native shared library.
Data source: live Odoo models (product, mrp, stock, sale, purchase).
Output: planned operations + demand pegging + resource load + auto-created
draft PO/MO/DO (closed-loop planning).

Full feature parity with frePPLe Community: master data (items, operations,
resources, buffers, calendars, setup matrices, suppliers), demand & forecast
(statistical methods, overrides, ABC/XYZ), inventory planning (safety stock,
reorder policies), planning execution (constrained/unconstrained, scenarios,
what-if), reports (resource/inventory/demand/KPI), API.
""",
    "author": "KOB",
    "website": "https://kissgroupbim.work",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "product",
        "stock",
        "mrp",
        "sale_management",
        "purchase",
    ],
    "data": [
        "security/thiti_security.xml",
        "security/ir.model.access.csv",
        "views/thiti_item_category_views.xml",
        "views/thiti_item_views.xml",
        "views/thiti_location_views.xml",
        "views/thiti_customer_views.xml",
        "views/thiti_supplier_views.xml",
        "views/thiti_calendar_views.xml",
        "views/thiti_resource_views.xml",
        "views/thiti_skill_views.xml",
        "views/thiti_buffer_views.xml",
        "views/thiti_operation_views.xml",
        "views/thiti_setup_matrix_views.xml",
        "views/thiti_demand_views.xml",
        "views/thiti_forecast_views.xml",
        "views/thiti_forecast_override_views.xml",
        "views/thiti_demand_aggregation_views.xml",
        "views/thiti_inventory_policy_views.xml",
        "views/thiti_abc_xyz_views.xml",
        "views/thiti_plan_run_views.xml",
        "views/thiti_plan_outputs_views.xml",
        "views/thiti_plan_replenishment_views.xml",
        "views/thiti_reports_views.xml",
        "views/thiti_dashboard_views.xml",
        "views/thiti_scenario_views.xml",
        "views/thiti_kob_brand_line_views.xml",
        "views/thiti_config_views.xml",
        "views/thiti_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kob_thiti_planning/static/src/scss/thiti.scss",
            "kob_thiti_planning/static/src/js/thiti_dashboard/**/*",
            "kob_thiti_planning/static/src/js/thiti_gantt/**/*",
        ],
    },
    "external_dependencies": {"python": ["lxml"]},
    "application": True,
    "installable": True,
    "auto_install": False,
}

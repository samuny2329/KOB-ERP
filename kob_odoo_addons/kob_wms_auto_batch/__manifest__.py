# -*- coding: utf-8 -*-
{
    "name": "KOB WMS — Auto Dispatch Batch (Round + Platform)",
    "version": "19.0.1.0.0",
    "category": "KOB ERP/Warehouse",
    "summary": (
        "Auto-group scan-Out into per-round, per-platform, per-courier "
        "courier batches. Adds dispatch-round concept and platform-aware "
        "batch routing on F4 Dispatch."
    ),
    "description": """
KOB WMS Auto Dispatch Batch
===========================
Extends kob_wms so that when an outbound scan ships an order via
`wms.sales.order.action_ship()`, the resulting `wms.scan.item` is
auto-routed into a `wms.courier.batch` keyed by:

    (active dispatch round, courier, platform)

Adds:
* `wms.dispatch.round` model (open/closed sessions)
* `dispatch_round_id` + `platform` fields on `wms.courier.batch`
* Override of `action_ship` that uses the compound key
* Cron that auto-creates today's round if none is open
* Settings flag to disable platform-grouping if business changes mind
""",
    "author": "Kiss of Beauty (KOB)",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "kob_wms",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/cron.xml",
        "views/dispatch_round_views.xml",
        "views/courier_batch_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "auto_install": False,
}

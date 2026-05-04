from odoo import api, fields, models


# Mirror the kob_wms platform selection so the field on the batch matches
# what `wms.sales.order.platform` already declares.
PLATFORM_SELECTION = [
    ("odoo", "Odoo"),
    ("shopee", "Shopee"),
    ("lazada", "Lazada"),
    ("tiktok", "TikTok"),
    ("pos", "Point of Sale"),
    ("manual", "Manual"),
]


class WmsCourierBatch(models.Model):
    _inherit = "wms.courier.batch"

    dispatch_round_id = fields.Many2one(
        "wms.dispatch.round",
        string="Dispatch Round",
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    platform = fields.Selection(
        PLATFORM_SELECTION,
        string="Platform",
        index=True,
        tracking=True,
        help="Sales platform this batch is dedicated to. "
             "Auto-set from the first scanned order's platform.",
    )
    round_label = fields.Char(
        related="dispatch_round_id.label",
        store=False,
        readonly=True,
    )
    round_state = fields.Selection(
        related="dispatch_round_id.state",
        store=True,
        readonly=True,
    )

    def action_dispatch(self):
        # Preserve original validation, then no-op extra hooks for now.
        return super().action_dispatch()


class WmsScanItem(models.Model):
    _inherit = "wms.scan.item"

    platform = fields.Selection(
        PLATFORM_SELECTION,
        string="Platform",
        index=True,
        help="Resolved platform of the source sales order.",
    )
    dispatch_round_id = fields.Many2one(
        related="batch_id.dispatch_round_id",
        store=True,
        readonly=True,
    )

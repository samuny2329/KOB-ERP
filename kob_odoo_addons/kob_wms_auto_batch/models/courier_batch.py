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

    expected_count = fields.Integer(
        compute="_compute_progress", store=True,
        help="Sum of expected_qty across scan items in the batch.",
    )
    scanned_done_count = fields.Integer(
        compute="_compute_progress", store=True,
        help="Sum of scanned_qty across scan items (physically scanned "
             "at the F4 Dispatch step).",
    )
    pending_count = fields.Integer(
        compute="_compute_progress", store=True,
        help="expected_count - scanned_done_count.",
    )
    completion_pct = fields.Float(
        compute="_compute_progress", store=True, digits=(5, 1),
        help="scanned_done_count / expected_count × 100.",
    )
    is_complete = fields.Boolean(
        compute="_compute_progress", store=True,
        help="True when every scan item has been physically scanned "
             "(scanned_qty >= expected_qty) — batch is ready to dispatch.",
    )

    @api.depends(
        "scan_item_ids",
        "scan_item_ids.expected_qty",
        "scan_item_ids.scanned_qty",
    )
    def _compute_progress(self):
        for b in self:
            expected = sum(b.scan_item_ids.mapped("expected_qty"))
            scanned = sum(min(si.scanned_qty, si.expected_qty)
                          for si in b.scan_item_ids)
            b.expected_count = expected
            b.scanned_done_count = scanned
            b.pending_count = max(0, expected - scanned)
            b.completion_pct = (scanned / expected * 100) if expected else 0.0
            b.is_complete = bool(expected) and scanned >= expected

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

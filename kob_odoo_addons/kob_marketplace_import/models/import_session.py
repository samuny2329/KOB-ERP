"""Persistent record per Marketplace Import run.

The wizard itself is transient and vacuumed after a few hours. This
model snapshots the result of every import so the user has:
    - history list of all import rounds
    - per-session summary (created / skipped / failed)
    - drill-down to the imported SOs and to the failed rows
    - link to the auto-created WMS courier batch (dispatch round)

Created by ``kob.marketplace.import.wizard.action_import`` at the end
of every run. Read-only thereafter.
"""
from odoo import api, fields, models, _


class KobMarketplaceImportSession(models.Model):
    _name = "kob.marketplace.import.session"
    _description = "Marketplace Import Session"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        required=True, readonly=True, default=lambda s: _("New"),
        copy=False,
    )
    user_id = fields.Many2one(
        "res.users", string="Imported By",
        default=lambda self: self.env.user, readonly=True,
    )
    date_started = fields.Datetime(readonly=True)
    date_finished = fields.Datetime(readonly=True)
    duration_sec = fields.Float(
        compute="_compute_duration", store=True,
        help="Time the import took, in seconds.",
    )

    platform = fields.Selection(
        [("shopee", "Shopee"), ("tiktok", "TikTok"),
         ("lazada", "Lazada"), ("manual", "Manual")],
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company", readonly=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse", readonly=True,
    )

    # File metadata
    file_count = fields.Integer(
        readonly=True,
        help="Number of xlsx/csv files uploaded in this batch.",
    )
    filenames = fields.Text(
        readonly=True,
        help="Newline-separated list of filenames processed.",
    )

    # Counters
    total_rows = fields.Integer(readonly=True, help="Total order-line rows scanned.")
    orders_attempted = fields.Integer(readonly=True)
    orders_created = fields.Integer(readonly=True)
    orders_skipped = fields.Integer(
        readonly=True,
        help="Orders that already existed in DB — duplicate by order_sn.",
    )
    orders_failed = fields.Integer(readonly=True)

    sale_order_ids = fields.Many2many(
        "sale.order", "kob_import_session_so_rel",
        "session_id", "so_id",
        string="Imported Sales Orders", readonly=True,
    )
    sale_order_count = fields.Integer(
        compute="_compute_counts", store=True)
    failure_ids = fields.One2many(
        "kob.marketplace.import.session.failure", "session_id",
        string="Failed Orders", readonly=True,
    )
    failure_count = fields.Integer(
        compute="_compute_counts", store=True)

    # Auto-created WMS batch
    wms_batch_id = fields.Many2one(
        "wms.courier.batch", string="WMS Dispatch Batch",
        readonly=True, ondelete="set null",
        help="Courier batch auto-created from successful SOs of this "
             "session. Worker validates this batch instead of touching "
             "individual orders.",
    )

    state = fields.Selection(
        [
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="running", readonly=True, tracking=True,
    )
    log = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "kob.marketplace.import.session"
                ) or _("MIS-%05d") % (
                    self.search_count([]) + 1
                )
        return super().create(vals_list)

    @api.depends("date_started", "date_finished")
    def _compute_duration(self):
        for s in self:
            if s.date_started and s.date_finished:
                delta = (s.date_finished - s.date_started).total_seconds()
                s.duration_sec = max(delta, 0.0)
            else:
                s.duration_sec = 0.0

    @api.depends("sale_order_ids", "failure_ids")
    def _compute_counts(self):
        for s in self:
            s.sale_order_count = len(s.sale_order_ids)
            s.failure_count = len(s.failure_ids)

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Imported Sales Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.sale_order_ids.ids)],
        }

    def action_view_failures(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Failed Orders"),
            "res_model": "kob.marketplace.import.session.failure",
            "view_mode": "list,form",
            "domain": [("session_id", "=", self.id)],
        }

    def action_view_batch(self):
        self.ensure_one()
        if not self.wms_batch_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Dispatch Batch"),
            "res_model": "wms.courier.batch",
            "res_id": self.wms_batch_id.id,
            "view_mode": "form",
        }


class KobMarketplaceImportSessionFailure(models.Model):
    _name = "kob.marketplace.import.session.failure"
    _description = "Marketplace Import — Failed Order Row"
    _order = "session_id desc, order_sn"

    session_id = fields.Many2one(
        "kob.marketplace.import.session", required=True,
        ondelete="cascade", index=True,
    )
    order_sn = fields.Char(string="Order ID", required=True, index=True)
    shop = fields.Char()
    sku = fields.Char()
    qty = fields.Float()
    error = fields.Char(required=True, help="Reason the row failed to import.")
    raw_row = fields.Text(
        help="Original xlsx row, JSON-encoded, for debugging / re-import.",
    )

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WmsDispatchRound(models.Model):
    """A dispatch round = a working session in which scan-Out events are
    grouped. Only one round per company is OPEN at a time; new scans
    auto-join the open round, and closing it forces the next scan to
    start a fresh round."""

    _name = "wms.dispatch.round"
    _description = "WMS Dispatch Round / Wave"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_open desc, id desc"

    name = fields.Char(
        required=True, copy=False, readonly=True,
        default=lambda s: _("New"),
    )
    label = fields.Char(
        help="Human-friendly label, e.g. 'Morning' or 'Round 1'.",
    )
    date_open = fields.Datetime(
        required=True, default=fields.Datetime.now, tracking=True,
    )
    date_close = fields.Datetime(readonly=True, tracking=True)
    state = fields.Selection(
        [("open", "Open"), ("closed", "Closed")],
        default="open", required=True, tracking=True, index=True,
    )
    batch_ids = fields.One2many(
        "wms.courier.batch", "dispatch_round_id", string="Batches",
    )
    batch_count = fields.Integer(compute="_compute_counts", store=True)
    scan_item_count = fields.Integer(compute="_compute_counts", store=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, required=True,
    )
    notes = fields.Text()

    _sql_constraints = [
        # We want only one open round per company. Use a partial index.
        # Implemented at app level too via _check_single_open.
    ]

    @api.depends("batch_ids", "batch_ids.scanned_count")
    def _compute_counts(self):
        for r in self:
            r.batch_count = len(r.batch_ids)
            r.scan_item_count = sum(b.scanned_count for b in r.batch_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get("name", _("New")) == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "wms.dispatch.round"
                )
                v["name"] = seq or fields.Datetime.now().strftime(
                    "Round-%Y%m%d-%H%M"
                )
        return super().create(vals_list)

    @api.constrains("state", "company_id")
    def _check_single_open(self):
        for r in self.filtered(lambda x: x.state == "open"):
            others = self.search([
                ("state", "=", "open"),
                ("company_id", "=", r.company_id.id),
                ("id", "!=", r.id),
            ])
            if others:
                raise UserError(_(
                    "Another dispatch round is already open for %(co)s: %(name)s. "
                    "Close it before starting a new one."
                ) % {"co": r.company_id.name, "name": others[0].name})

    def action_close(self):
        for r in self:
            if r.state != "open":
                continue
            r.write({
                "state": "closed",
                "date_close": fields.Datetime.now(),
            })

    def action_reopen(self):
        for r in self:
            if r.state == "closed":
                # Refuse if there's already an open round for the same company
                open_round = self.search([
                    ("state", "=", "open"),
                    ("company_id", "=", r.company_id.id),
                ], limit=1)
                if open_round:
                    raise UserError(_(
                        "Cannot reopen — round %s is currently open."
                    ) % open_round.name)
                r.write({"state": "open", "date_close": False})

    @api.model
    def get_or_create_active(self, company=None):
        """Return the open round for the given company, creating one if
        no round is currently open. Used by action_ship override."""
        company = company or self.env.company
        existing = self.search([
            ("state", "=", "open"),
            ("company_id", "=", company.id),
        ], limit=1)
        if existing:
            return existing
        return self.sudo().create({
            "company_id": company.id,
            "label": fields.Datetime.now().strftime("Auto %Y-%m-%d %H:%M"),
        })

    @api.model
    def cron_auto_open_today(self):
        """Cron entry — make sure there is always an open round per company.
        Runs every 15 min as a safety net."""
        for company in self.env["res.company"].sudo().search([]):
            self.get_or_create_active(company)
        return True

    def action_open_batches(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Batches in %s") % self.name,
            "res_model": "wms.courier.batch",
            "view_mode": "list,form",
            "domain": [("dispatch_round_id", "=", self.id)],
            "context": {"default_dispatch_round_id": self.id},
        }

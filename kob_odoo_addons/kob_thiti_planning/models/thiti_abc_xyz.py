from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ThitiAbcXyzConfig(models.Model):
    _name = "thiti.abc.xyz.config"
    _description = "Thiti ABC/XYZ Classification Settings"
    _inherit = ["mail.thread"]
    _rec_name = "name"

    name = fields.Char(required=True, default="Default ABC/XYZ", tracking=True)
    abc_method = fields.Selection(
        [("revenue", "Revenue"),
         ("volume", "Volume"),
         ("count", "Order count")],
        default="revenue", required=True, tracking=True,
    )
    abc_a_threshold_pct = fields.Float(
        string="A cum. % cutoff", default=80.0, tracking=True,
        help="Items contributing the top X% of metric → class A.",
    )
    abc_b_threshold_pct = fields.Float(
        string="B cum. % cutoff", default=95.0, tracking=True,
        help="Cumulative cutoff for class B (rest = C).",
    )
    xyz_method = fields.Selection(
        [("cv", "Coefficient of Variation (σ/μ)"),
         ("range_pct", "Range %"),
         ("zero_ratio", "Zero-demand ratio")],
        default="cv", required=True, tracking=True,
    )
    xyz_x_threshold = fields.Float(
        string="X CV cutoff", default=0.5, tracking=True,
        help="CV ≤ X cutoff → predictable (X class).",
    )
    xyz_y_threshold = fields.Float(
        string="Y CV cutoff", default=1.0, tracking=True,
        help="CV ≤ Y cutoff → variable (Y); above = unpredictable (Z).",
    )
    history_days = fields.Integer(
        default=365, tracking=True,
        help="Look-back window in days for historical demand.",
    )
    last_run = fields.Datetime(readonly=True)
    last_run_user_id = fields.Many2one("res.users", readonly=True)
    items_classified = fields.Integer(readonly=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         _("Configuration name must be unique per company.")),
    ]

    @api.constrains("abc_a_threshold_pct", "abc_b_threshold_pct")
    def _check_abc_order(self):
        for rec in self:
            if not 0 < rec.abc_a_threshold_pct < rec.abc_b_threshold_pct <= 100:
                raise ValidationError(
                    _("ABC thresholds must satisfy 0 < A < B ≤ 100.")
                )

    @api.constrains("xyz_x_threshold", "xyz_y_threshold")
    def _check_xyz_order(self):
        for rec in self:
            if not 0 <= rec.xyz_x_threshold < rec.xyz_y_threshold:
                raise ValidationError(
                    _("XYZ thresholds must satisfy 0 ≤ X < Y.")
                )

    def action_classify(self):
        """Trigger classification batch — placeholder.

        Full implementation in Phase 5 (after data collector + history fetcher).
        Runs sale.order history through the configured method and updates
        thiti.item.abc_class / xyz_class.
        """
        self.ensure_one()
        self.write({
            "last_run": fields.Datetime.now(),
            "last_run_user_id": self.env.user.id,
            "items_classified": 0,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ABC/XYZ Classification"),
                "message": _("Classification engine not wired yet. "
                             "Implemented in Phase 5 (data collector)."),
                "type": "warning",
                "sticky": False,
            },
        }

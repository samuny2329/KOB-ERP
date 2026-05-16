from odoo import _, api, fields, models


OVERRIDE_REASON = [
    ("promo", "Promotion"),
    ("seasonality", "Seasonality"),
    ("ndp", "New Product"),
    ("eol", "End-of-Life"),
    ("knowledge", "Sales Knowledge"),
    ("event", "Event"),
    ("correction", "Forecast Correction"),
    ("other", "Other"),
]


class ThitiForecastOverride(models.Model):
    _name = "thiti.forecast.override"
    _description = "Thiti Forecast Override (audit trail)"
    _inherit = ["mail.thread"]
    _order = "forecast_id, write_date desc"

    forecast_id = fields.Many2one(
        "thiti.forecast", required=True, index=True, ondelete="cascade", tracking=True,
    )
    item_id = fields.Many2one(
        related="forecast_id.item_id", store=True, index=True,
    )
    location_id = fields.Many2one(
        related="forecast_id.location_id", store=True, index=True,
    )
    bucket_start = fields.Date(related="forecast_id.bucket_start", store=True)
    bucket_end = fields.Date(related="forecast_id.bucket_end", store=True)
    previous_qty = fields.Float(string="Previous Qty", readonly=True)
    new_qty = fields.Float(string="New Qty", required=True, tracking=True)
    delta_qty = fields.Float(compute="_compute_delta", store=True)
    reason = fields.Selection(OVERRIDE_REASON, default="correction", required=True, tracking=True)
    user_id = fields.Many2one(
        "res.users", default=lambda s: s.env.user, required=True, tracking=True,
    )
    comment = fields.Text(tracking=True)
    company_id = fields.Many2one(
        related="forecast_id.company_id", store=True, index=True,
    )

    @api.depends("new_qty", "previous_qty")
    def _compute_delta(self):
        for rec in self:
            rec.delta_qty = rec.new_qty - (rec.previous_qty or 0.0)

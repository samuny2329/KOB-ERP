from odoo import _, api, fields, models


FORECAST_METHOD = [
    ("manual", "Manual"),
    ("constant", "Constant"),
    ("moving_average", "Moving Average"),
    ("single_exp", "Single Exponential Smoothing"),
    ("double_exp", "Double Exponential Smoothing (Holt)"),
    ("seasonal", "Seasonal (Holt-Winters)"),
    ("croston", "Croston (intermittent)"),
    ("auto", "Auto-select"),
]

DEMAND_PATTERN = [
    ("smooth", "Smooth"),
    ("erratic", "Erratic"),
    ("intermittent", "Intermittent"),
    ("lumpy", "Lumpy"),
]


class ThitiForecast(models.Model):
    _name = "thiti.forecast"
    _description = "Thiti Forecast (item × location × customer × bucket)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "item_id, location_id, customer_id, bucket_start"
    _rec_name = "display_name"

    name = fields.Char(index=True)
    item_id = fields.Many2one(
        "thiti.item", required=True, index=True, ondelete="cascade", tracking=True,
    )
    location_id = fields.Many2one(
        "thiti.location", required=True, index=True, ondelete="cascade", tracking=True,
    )
    customer_id = fields.Many2one(
        "thiti.customer", index=True, ondelete="set null", tracking=True,
    )
    bucket_start = fields.Date(required=True, index=True, tracking=True)
    bucket_end = fields.Date(required=True, index=True, tracking=True)
    bucket_label = fields.Char(
        help="Display label for the bucket (e.g. '2026-W23', '2026-06')."
    )

    forecast_method = fields.Selection(
        FORECAST_METHOD, default="auto", required=True, tracking=True,
    )
    demand_pattern = fields.Selection(
        DEMAND_PATTERN, compute="_compute_pattern", store=True, index=True,
    )

    history_qty = fields.Float(
        string="Historical Demand",
        help="Actual demand observed in this bucket (loaded from sale.order).",
    )
    baseline_qty = fields.Float(
        string="Statistical Baseline",
        help="Computed by selected forecast method.",
    )
    override_qty = fields.Float(
        string="Override",
        default=-1.0,
        help="Manual override (-1 means no override; use baseline).",
    )
    net_qty = fields.Float(
        string="Net Forecast",
        compute="_compute_net", store=True,
        help="Effective forecast after override + net-down by actual orders.",
    )
    consumed_qty = fields.Float(
        string="Consumed by Orders",
        help="Portion already covered by confirmed sale.order.line for this bucket.",
    )
    total_qty = fields.Float(
        string="Total (forecast + orders)",
        compute="_compute_total", store=True,
    )

    bias = fields.Float(
        readonly=True,
        help="Forecast bias = mean(actual - forecast). Negative=over-forecast.",
    )
    mape = fields.Float(
        string="MAPE %",
        readonly=True,
        help="Mean Absolute Percent Error over training window.",
    )
    rmse = fields.Float(
        string="RMSE",
        readonly=True,
        help="Root Mean Squared Error over training window.",
    )
    smape = fields.Float(
        string="sMAPE %",
        readonly=True,
        help="Symmetric MAPE.",
    )

    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        ("bucket_unique",
         "UNIQUE(item_id, location_id, customer_id, bucket_start, company_id)",
         _("Duplicate forecast bucket for item-location-customer-period.")),
    ]

    @api.depends("item_id", "location_id", "customer_id", "bucket_label", "bucket_start")
    def _compute_display_name(self):
        for rec in self:
            label = rec.bucket_label or (rec.bucket_start.isoformat() if rec.bucket_start else "")
            parts = [rec.item_id.name or "?", rec.location_id.name or "?", label]
            if rec.customer_id:
                parts.insert(2, rec.customer_id.name)
            rec.display_name = " / ".join(p for p in parts if p)

    @api.depends("override_qty", "baseline_qty", "consumed_qty")
    def _compute_net(self):
        for rec in self:
            chosen = rec.override_qty if rec.override_qty >= 0 else rec.baseline_qty
            rec.net_qty = max(chosen - rec.consumed_qty, 0.0)

    @api.depends("net_qty", "consumed_qty")
    def _compute_total(self):
        for rec in self:
            rec.total_qty = rec.net_qty + rec.consumed_qty

    @api.depends("history_qty")
    def _compute_pattern(self):
        # Placeholder — full classification done by engine in Phase 5.
        # Heuristic: zero history → intermittent.
        for rec in self:
            rec.demand_pattern = "intermittent" if not rec.history_qty else "smooth"

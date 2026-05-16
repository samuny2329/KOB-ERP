from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


REORDER_METHOD = [
    ("rop", "Reorder Point (ROP)"),
    ("minmax", "Min-Max"),
    ("periodic", "Periodic Review"),
    ("kanban", "Kanban (signal-based)"),
    ("mts", "Make-to-Stock"),
    ("mto", "Make-to-Order"),
]

SAFETY_STOCK_METHOD = [
    ("fixed", "Fixed Quantity"),
    ("days_of_supply", "Days of Supply"),
    ("service_level", "Service Level (statistical)"),
    ("std_dev", "k × σ of demand"),
    ("manual_override", "Manual Override"),
]


class ThitiInventoryPolicy(models.Model):
    _name = "thiti.inventory.policy"
    _description = "Thiti Inventory Policy (per buffer)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "buffer_id"
    _rec_name = "display_name"

    buffer_id = fields.Many2one(
        "thiti.buffer", required=True, index=True, ondelete="cascade", tracking=True,
    )
    item_id = fields.Many2one(
        related="buffer_id.item_id", store=True, index=True,
    )
    location_id = fields.Many2one(
        related="buffer_id.location_id", store=True, index=True,
    )
    reorder_method = fields.Selection(
        REORDER_METHOD, default="rop", required=True, tracking=True,
    )
    safety_stock_method = fields.Selection(
        SAFETY_STOCK_METHOD, default="days_of_supply", required=True, tracking=True,
    )
    service_level_pct = fields.Float(
        string="Service Level %", default=95.0, tracking=True,
        help="Target probability of not stocking out (0-100).",
    )
    safety_stock_days = fields.Float(default=7.0, tracking=True)
    safety_stock_qty = fields.Float(default=0.0, tracking=True)
    safety_stock_k = fields.Float(
        string="k (σ multiplier)", default=1.65,
        help="Multiplier for standard deviation. 1.65≈95%, 2.33≈99%.",
    )
    reorder_point = fields.Float(
        compute="_compute_reorder", store=True, readonly=False,
        help="Trigger replenishment when on-hand ≤ ROP.",
    )
    reorder_qty = fields.Float(
        compute="_compute_reorder", store=True, readonly=False,
        help="Quantity to replenish per cycle.",
    )
    review_period_days = fields.Float(default=7.0)
    max_inventory = fields.Float()
    eoq_holding_cost_pct = fields.Float(
        string="Holding Cost %/yr", default=20.0,
        help="Annual holding cost as percent of item cost.",
    )
    eoq_order_cost = fields.Float(
        string="Order Cost",
        help="Fixed cost per order (used for EOQ).",
    )
    eoq_qty = fields.Float(
        compute="_compute_eoq", store=True,
        help="Economic Order Quantity.",
    )
    avg_demand_per_day = fields.Float(
        help="Mean daily demand from history (computed by classification cron).",
    )
    demand_std_dev = fields.Float(
        help="Standard deviation of daily demand (computed by classification cron).",
    )
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        related="buffer_id.company_id", store=True, index=True,
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        ("buffer_unique", "UNIQUE(buffer_id)",
         _("Only one inventory policy per buffer.")),
    ]

    @api.depends("buffer_id.display_name", "reorder_method")
    def _compute_display_name(self):
        for rec in self:
            base = rec.buffer_id.display_name or _("Policy")
            method = dict(REORDER_METHOD).get(rec.reorder_method, "")
            rec.display_name = f"{base} [{method}]"

    @api.depends(
        "safety_stock_method",
        "safety_stock_qty",
        "safety_stock_days",
        "safety_stock_k",
        "avg_demand_per_day",
        "demand_std_dev",
        "buffer_id.leadtime_days",
    )
    def _compute_reorder(self):
        for rec in self:
            ss = rec._compute_safety_stock()
            lt = rec.buffer_id.leadtime_days or 0.0
            avg = rec.avg_demand_per_day or 0.0
            rec.reorder_point = ss + avg * lt
            rec.reorder_qty = avg * (lt + (rec.review_period_days or 0.0))

    def _compute_safety_stock(self) -> float:
        self.ensure_one()
        method = self.safety_stock_method
        if method == "fixed":
            return self.safety_stock_qty
        if method == "manual_override":
            return self.safety_stock_qty
        if method == "days_of_supply":
            return (self.safety_stock_days or 0.0) * (self.avg_demand_per_day or 0.0)
        if method in ("service_level", "std_dev"):
            lt = self.buffer_id.leadtime_days or 0.0
            sigma = self.demand_std_dev or 0.0
            return self.safety_stock_k * sigma * (lt ** 0.5)
        return 0.0

    @api.depends(
        "eoq_holding_cost_pct",
        "eoq_order_cost",
        "avg_demand_per_day",
        "item_id.cost",
    )
    def _compute_eoq(self):
        for rec in self:
            cost = rec.item_id.cost or 0.0
            annual_demand = (rec.avg_demand_per_day or 0.0) * 365.0
            holding = cost * (rec.eoq_holding_cost_pct or 0.0) / 100.0
            order_cost = rec.eoq_order_cost or 0.0
            if holding > 0 and annual_demand > 0 and order_cost > 0:
                rec.eoq_qty = (2.0 * annual_demand * order_cost / holding) ** 0.5
            else:
                rec.eoq_qty = 0.0

    @api.constrains("service_level_pct")
    def _check_service_level(self):
        for rec in self:
            if not 0.0 <= rec.service_level_pct <= 100.0:
                raise ValidationError(_("Service level must be between 0 and 100."))

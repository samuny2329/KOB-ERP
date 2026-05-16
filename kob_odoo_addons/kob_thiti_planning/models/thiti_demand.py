from odoo import _, fields, models


DEMAND_STATUS = [
    ("inquiry", "Inquiry"),
    ("quote", "Quote"),
    ("open", "Open"),
    ("closed", "Closed"),
    ("canceled", "Canceled"),
]

DEMAND_POLICY = [
    ("independent", "Independent"),
    ("alltogether", "All Together"),
    ("inratio", "In Ratio"),
]


class ThitiDemand(models.Model):
    _name = "thiti.demand"
    _description = "Thiti Planning Demand"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "due, priority, item_id"

    name = fields.Char(required=True, index=True, tracking=True)
    item_id = fields.Many2one(
        "thiti.item", required=True, index=True, ondelete="restrict", tracking=True,
    )
    location_id = fields.Many2one(
        "thiti.location", index=True, ondelete="restrict", tracking=True,
    )
    customer_id = fields.Many2one(
        "thiti.customer", index=True, ondelete="set null", tracking=True,
    )
    quantity = fields.Float(required=True, default=0.0, tracking=True)
    due = fields.Datetime(required=True, index=True, tracking=True)
    priority = fields.Integer(default=10, tracking=True)
    minshipment = fields.Float(string="Min Shipment Qty")
    maxlateness_days = fields.Float(string="Max Lateness (days)")
    status = fields.Selection(DEMAND_STATUS, default="open", required=True, tracking=True)
    policy = fields.Selection(DEMAND_POLICY, default="independent", required=True)
    operation_id = fields.Many2one(
        "thiti.operation", string="Forced Operation", index=True,
    )
    delivery_id = fields.Many2one(
        "thiti.operation", string="Forced Delivery Op", index=True,
    )
    odoo_sale_line_id = fields.Many2one(
        "sale.order.line", string="Linked Sale Order Line",
        index=True, ondelete="set null", tracking=True,
    )
    odoo_sale_order_id = fields.Many2one(
        related="odoo_sale_line_id.order_id", string="Sale Order",
        store=True, index=True,
    )
    plan_quantity = fields.Float(
        readonly=True,
        help="Planned quantity from latest solver output.",
    )
    plan_due = fields.Datetime(
        readonly=True,
        help="Planned delivery date from latest solver output.",
    )
    plan_late_days = fields.Float(
        readonly=True,
        help="Lateness in days (positive=late, negative=early).",
    )
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         _("Demand name must be unique per company.")),
    ]

from odoo import _, fields, models


BUFFER_TYPE = [
    ("default", "Default"),
    ("procure", "Procure"),
    ("infinite", "Infinite"),
]


class ThitiBuffer(models.Model):
    _name = "thiti.buffer"
    _description = "Thiti Planning Buffer (item × location)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "item_id, location_id"
    _rec_name = "display_name"

    item_id = fields.Many2one(
        "thiti.item", required=True, index=True, ondelete="cascade", tracking=True,
    )
    location_id = fields.Many2one(
        "thiti.location", required=True, index=True, ondelete="cascade", tracking=True,
    )
    buffer_type = fields.Selection(
        BUFFER_TYPE, default="default", required=True, tracking=True,
    )
    onhand = fields.Float(
        string="On Hand", default=0.0, tracking=True,
        help="Initial on-hand stock at plan start.",
    )
    minimum = fields.Float(string="Safety Stock", default=0.0, tracking=True)
    maximum = fields.Float(string="Max Inventory", default=0.0, tracking=True)
    min_calendar_id = fields.Many2one(
        "thiti.calendar", string="Time-varying Min Calendar",
    )
    leadtime_days = fields.Float(default=0.0, tracking=True)
    fence_days = fields.Float(
        default=0.0,
        help="Lead-time fence — no new operationplans before fence date.",
    )
    sizeminimum = fields.Float(string="Min Order Qty", default=1.0)
    sizemultiple = fields.Float(string="Order Multiple", default=1.0)
    sizemaximum = fields.Float(string="Max Order Qty")
    lotsize_rule = fields.Selection(
        [("foq", "Fixed Order Qty"),
         ("poq", "Periodic Order Qty"),
         ("lfl", "Lot-for-Lot"),
         ("eoq", "Economic Order Qty")],
        default="lfl",
    )
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        ("item_location_unique", "UNIQUE(item_id, location_id, company_id)",
         _("Buffer already exists for this item-location pair.")),
    ]

    def _compute_display_name(self):
        for rec in self:
            item = rec.item_id.name or ""
            loc = rec.location_id.name or ""
            rec.display_name = f"{item} @ {loc}" if item or loc else _("Buffer")

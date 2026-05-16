from odoo import _, fields, models


OPERATION_TYPE = [
    ("fixed_time", "Fixed Time"),
    ("time_per", "Time per Unit"),
    ("routing", "Routing"),
    ("alternate", "Alternate"),
    ("split", "Split"),
]


class ThitiOperation(models.Model):
    _name = "thiti.operation"
    _description = "Thiti Planning Operation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, index=True, tracking=True)
    operation_type = fields.Selection(
        OPERATION_TYPE, default="fixed_time", required=True, tracking=True,
    )
    bom_id = fields.Many2one(
        "mrp.bom", string="Linked BOM", index=True, tracking=True,
    )
    item_id = fields.Many2one(
        "thiti.item", string="Output Item", index=True, tracking=True,
    )
    location_id = fields.Many2one(
        "thiti.location", string="Location", index=True, tracking=True,
    )
    duration_hours = fields.Float(string="Fixed Duration (h)", tracking=True)
    duration_per_hours = fields.Float(string="Time per Unit (h)", tracking=True)
    sizeminimum = fields.Float(string="Min Lot", default=1.0)
    sizemultiple = fields.Float(string="Lot Multiple", default=1.0)
    sizemaximum = fields.Float(string="Max Lot")
    cost = fields.Float(tracking=True)
    priority = fields.Integer(default=1, tracking=True)
    effective_start = fields.Datetime()
    effective_end = fields.Datetime()
    posttime_hours = fields.Float(string="Post-time (h)")
    pretime_hours = fields.Float(string="Pre-time (h)")
    search_mode = fields.Selection(
        [("priority", "Priority"), ("minlateness", "Min Lateness"),
         ("mincost", "Min Cost")],
        default="priority",
    )
    flow_ids = fields.One2many("thiti.flow", "operation_id", string="Flows")
    load_ids = fields.One2many("thiti.load", "operation_id", string="Loads")
    step_ids = fields.One2many(
        "thiti.operation.step", "operation_id", string="Sub-Operations",
    )
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         _("Operation name must be unique per company.")),
    ]

from odoo import _, fields, models


RESOURCE_TYPE = [
    ("default", "Default"),
    ("buckets", "Buckets"),
    ("time_per", "Time-per"),
    ("infinite", "Infinite"),
]


class ThitiResource(models.Model):
    _name = "thiti.resource"
    _description = "Thiti Planning Resource"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, index=True, tracking=True)
    code = fields.Char(index=True)
    resource_type = fields.Selection(
        RESOURCE_TYPE, default="default", required=True, tracking=True,
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter", string="Linked Workcenter", index=True, tracking=True,
    )
    location_id = fields.Many2one(
        "thiti.location", string="Location", index=True, tracking=True,
    )
    calendar_id = fields.Many2one(
        "thiti.calendar", string="Available Calendar", index=True,
    )
    maximum = fields.Float(
        string="Capacity", default=1.0, tracking=True,
        help="Capacity of the resource (units in parallel).",
    )
    cost_per_hour = fields.Float(tracking=True)
    setup_matrix_id = fields.Many2one("thiti.setup.matrix", string="Setup Matrix")
    efficiency = fields.Float(default=100.0, help="Efficiency in percent.")
    skill_ids = fields.One2many(
        "thiti.resource.skill", "resource_id", string="Skills",
    )
    load_ids = fields.One2many("thiti.load", "resource_id", string="Loads")
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         _("Resource name must be unique per company.")),
    ]

from odoo import _, fields, models


class ThitiLoad(models.Model):
    _name = "thiti.load"
    _description = "Thiti Load (operation → resource capacity load)"
    _order = "operation_id, resource_id"

    operation_id = fields.Many2one(
        "thiti.operation", required=True, index=True, ondelete="cascade",
    )
    resource_id = fields.Many2one(
        "thiti.resource", required=True, index=True, ondelete="restrict",
    )
    quantity = fields.Float(
        default=1.0,
        help="Resource units consumed by this operation.",
    )
    priority = fields.Integer(default=1)
    name_alt = fields.Char(string="Alternate Group")
    skill_id = fields.Many2one("thiti.skill", index=True)
    setup_id = fields.Many2one("thiti.setup.matrix", string="Setup Matrix")
    search_mode = fields.Selection(
        [("priority", "Priority"), ("minlateness", "Min Lateness"),
         ("mincost", "Min Cost")],
        default="priority",
    )
    effective_start = fields.Datetime()
    effective_end = fields.Datetime()

from odoo import _, fields, models


class ThitiSetupRule(models.Model):
    _name = "thiti.setup.rule"
    _description = "Thiti Setup Rule (changeover time matrix entry)"
    _order = "matrix_id, priority"

    matrix_id = fields.Many2one(
        "thiti.setup.matrix", required=True, index=True, ondelete="cascade",
    )
    priority = fields.Integer(default=1)
    from_setup = fields.Char(required=True, index=True)
    to_setup = fields.Char(required=True, index=True)
    duration_hours = fields.Float(default=0.0)
    cost = fields.Float(default=0.0)
    resource_id = fields.Many2one("thiti.resource", index=True)

    _sql_constraints = [
        ("from_to_unique",
         "UNIQUE(matrix_id, from_setup, to_setup, priority)",
         _("Duplicate setup rule for same from/to pair.")),
    ]

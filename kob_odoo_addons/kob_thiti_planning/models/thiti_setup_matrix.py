from odoo import _, fields, models


class ThitiSetupMatrix(models.Model):
    _name = "thiti.setup.matrix"
    _description = "Thiti Setup Matrix"
    _order = "name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    rule_ids = fields.One2many("thiti.setup.rule", "matrix_id", string="Rules")
    note = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         _("Setup matrix name must be unique per company.")),
    ]

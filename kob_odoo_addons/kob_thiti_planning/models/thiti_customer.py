from odoo import _, fields, models


class ThitiCustomer(models.Model):
    _name = "thiti.customer"
    _description = "Thiti Planning Customer"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, index=True, tracking=True)
    code = fields.Char(index=True)
    partner_id = fields.Many2one(
        "res.partner", string="Linked Partner", index=True,
        domain=[("customer_rank", ">", 0)], tracking=True,
    )
    priority = fields.Integer(default=1, tracking=True)
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         _("Customer name must be unique per company.")),
    ]

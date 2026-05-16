from odoo import _, fields, models


class ThitiSupplier(models.Model):
    _name = "thiti.supplier"
    _description = "Thiti Planning Supplier"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, index=True, tracking=True)
    code = fields.Char(index=True)
    partner_id = fields.Many2one(
        "res.partner", string="Linked Partner", index=True,
        domain=[("supplier_rank", ">", 0)], tracking=True,
    )
    calendar_id = fields.Many2one(
        "thiti.calendar", string="Available Calendar", index=True,
    )
    lead_time_days = fields.Float(default=0.0, tracking=True)
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         _("Supplier name must be unique per company.")),
    ]

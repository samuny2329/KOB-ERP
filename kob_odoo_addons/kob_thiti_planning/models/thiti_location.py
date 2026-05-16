from odoo import _, fields, models


class ThitiLocation(models.Model):
    _name = "thiti.location"
    _description = "Thiti Planning Location"
    _inherit = ["mail.thread"]
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "complete_name"
    _order = "complete_name"

    name = fields.Char(required=True, index=True, tracking=True)
    code = fields.Char(index=True)
    complete_name = fields.Char(compute="_compute_complete_name", store=True)
    parent_id = fields.Many2one(
        "thiti.location", "Parent", index=True, ondelete="restrict", tracking=True,
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("thiti.location", "parent_id", "Children")
    warehouse_id = fields.Many2one(
        "stock.warehouse", string="Linked Warehouse", index=True, tracking=True,
    )
    odoo_location_id = fields.Many2one(
        "stock.location", string="Linked Odoo Location", index=True, tracking=True,
    )
    calendar_id = fields.Many2one(
        "thiti.calendar", string="Operating Calendar", index=True,
    )
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)",
         _("Location name must be unique per company.")),
    ]

    def _compute_complete_name(self):
        for rec in self:
            parts = []
            cur = rec
            while cur:
                parts.append(cur.name or "")
                cur = cur.parent_id
            rec.complete_name = " / ".join(reversed(parts))

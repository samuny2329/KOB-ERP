from odoo import _, api, fields, models


class ThitiItem(models.Model):
    _name = "thiti.item"
    _description = "Thiti Planning Item"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, index=True, tracking=True)
    description = fields.Char(tracking=True)
    product_id = fields.Many2one(
        "product.product", string="Linked Odoo Product",
        index=True, ondelete="restrict", tracking=True,
    )
    category_id = fields.Many2one(
        "thiti.item.category", string="Category", index=True, tracking=True,
    )
    uom_id = fields.Many2one(
        related="product_id.uom_id", string="UoM", readonly=True,
    )
    cost = fields.Float(tracking=True, digits="Product Price")
    price = fields.Float(tracking=True, digits="Product Price")
    abc_class = fields.Selection(
        [("a", "A"), ("b", "B"), ("c", "C")], compute="_compute_abc_xyz", store=True,
    )
    xyz_class = fields.Selection(
        [("x", "X"), ("y", "Y"), ("z", "Z")], compute="_compute_abc_xyz", store=True,
    )
    abc_xyz = fields.Char(compute="_compute_abc_xyz", store=True, index=True)
    volume = fields.Float()
    weight = fields.Float()
    note = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name, company_id)", _("Item name must be unique per company.")),
    ]

    @api.depends("abc_class", "xyz_class")
    def _compute_abc_xyz(self):
        # Placeholder — real ABC/XYZ computed in Group C (inventory).
        for rec in self:
            rec.abc_xyz = (
                f"{(rec.abc_class or '-').upper()}{(rec.xyz_class or '-').upper()}"
            )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and not self.name:
            self.name = self.product_id.default_code or self.product_id.name
        if self.product_id and not self.description:
            self.description = self.product_id.name
        if self.product_id and not self.cost:
            self.cost = self.product_id.standard_price

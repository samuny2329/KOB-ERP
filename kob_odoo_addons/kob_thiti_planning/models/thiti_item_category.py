from odoo import _, fields, models


class ThitiItemCategory(models.Model):
    _name = "thiti.item.category"
    _description = "Thiti Item Category"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "complete_name"
    _order = "complete_name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    complete_name = fields.Char(compute="_compute_complete_name", store=True)
    parent_id = fields.Many2one(
        "thiti.item.category", "Parent", index=True, ondelete="restrict"
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("thiti.item.category", "parent_id", "Children")
    odoo_categ_id = fields.Many2one(
        "product.category", string="Linked Odoo Category", index=True
    )
    item_count = fields.Integer(compute="_compute_item_count")
    note = fields.Text()

    _sql_constraints = [
        ("name_unique", "UNIQUE(name)", _("Category name must be unique.")),
    ]

    def _compute_complete_name(self):
        for rec in self:
            parts = []
            cur = rec
            while cur:
                parts.append(cur.name or "")
                cur = cur.parent_id
            rec.complete_name = " / ".join(reversed(parts))

    def _compute_item_count(self):
        groups = self.env["thiti.item"]._read_group(
            [("category_id", "in", self.ids)],
            groupby=["category_id"],
            aggregates=["__count"],
        )
        counts = {category.id: count for category, count in groups}
        for rec in self:
            rec.item_count = counts.get(rec.id, 0)

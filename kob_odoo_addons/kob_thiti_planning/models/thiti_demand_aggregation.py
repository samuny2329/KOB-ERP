from odoo import _, fields, models


AGGREGATION_LEVEL = [
    ("brand", "Brand"),
    ("family", "Family"),
    ("subfamily", "Sub-family"),
    ("region", "Region"),
    ("channel", "Channel"),
    ("custom", "Custom"),
]


class ThitiDemandAggregation(models.Model):
    _name = "thiti.demand.aggregation"
    _description = "Thiti Demand Aggregation (product family hierarchy)"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "complete_name"
    _order = "complete_name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    complete_name = fields.Char(compute="_compute_complete_name", store=True)
    parent_id = fields.Many2one(
        "thiti.demand.aggregation", "Parent", index=True, ondelete="restrict",
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        "thiti.demand.aggregation", "parent_id", "Children",
    )
    level = fields.Selection(
        AGGREGATION_LEVEL, default="family", required=True, index=True,
    )
    item_ids = fields.Many2many(
        "thiti.item",
        "thiti_aggregation_item_rel",
        "aggregation_id",
        "item_id",
        string="Items",
    )
    location_ids = fields.Many2many(
        "thiti.location",
        "thiti_aggregation_location_rel",
        "aggregation_id",
        "location_id",
        string="Locations",
    )
    customer_ids = fields.Many2many(
        "thiti.customer",
        "thiti_aggregation_customer_rel",
        "aggregation_id",
        "customer_id",
        string="Customers",
    )
    item_count = fields.Integer(compute="_compute_counts")
    note = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("name_level_unique", "UNIQUE(name, level, company_id)",
         _("Aggregation name must be unique per level and company.")),
    ]

    def _compute_complete_name(self):
        for rec in self:
            parts = []
            cur = rec
            while cur:
                parts.append(cur.name or "")
                cur = cur.parent_id
            rec.complete_name = " / ".join(reversed(parts))

    def _compute_counts(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)

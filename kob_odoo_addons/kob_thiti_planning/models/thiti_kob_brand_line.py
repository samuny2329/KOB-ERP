"""KOB-specific: SWB/SWH brand line + LWN-190A reusable crate pool.

Extends the generic frePPLe model with KOB business rules:
- Brand line classification (SWB = Skin Whitening Bottle, SWH = Skin Whitening Hand-cream)
- Boat carrier flag — partners shipped by boat get extended lead time / pallet rules
- LWN-190A reusable crate (30 bottles, 4kg empty) tracked as resource for forklift capacity
"""
from __future__ import annotations

from odoo import _, fields, models


class ThitiKobBrandLine(models.Model):
    _name = "thiti.kob.brand.line"
    _description = "KOB Brand Line (SWB/SWH/etc.)"
    _inherit = ["mail.thread"]
    _order = "code"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, tracking=True)
    full_name = fields.Char(tracking=True,
                            help="e.g. Skin Whitening Bottle (SWB).")
    boat_carrier = fields.Boolean(
        default=False, tracking=True,
        help="True when typical shipping route uses boat carriers — "
             "adds extra lead-time + pallet count rules in collector.",
    )
    crate_required = fields.Boolean(
        default=False, tracking=True,
        help="True when SKU uses LWN-190A reusable crate (vs disposable carton).",
    )
    bottles_per_crate = fields.Integer(default=30)
    crate_weight_kg = fields.Float(default=4.0)
    extra_leadtime_days = fields.Float(default=0.0)
    item_ids = fields.One2many("thiti.item", "kob_brand_line_id",
                               string="Items in this brand line")
    item_count = fields.Integer(compute="_compute_count")
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
    )

    _sql_constraints = [
        ("code_unique", "UNIQUE(code, company_id)",
         "Brand line code must be unique per company."),
    ]

    def _compute_count(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)


class ThitiItemKob(models.Model):
    _inherit = "thiti.item"

    kob_brand_line_id = fields.Many2one(
        "thiti.kob.brand.line", string="KOB Brand Line", index=True, tracking=True,
    )
    crate_required = fields.Boolean(
        related="kob_brand_line_id.crate_required", store=True,
    )
    bottles_per_crate = fields.Integer(
        related="kob_brand_line_id.bottles_per_crate", store=True,
    )

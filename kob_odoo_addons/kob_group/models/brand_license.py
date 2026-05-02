# -*- coding: utf-8 -*-
"""Brand license — which company has the right to sell which brand."""

from odoo import api, fields, models, _


class KobBrandLicense(models.Model):
    _name = "kob.brand.license"
    _description = "Brand License"
    _order = "brand_code, company_id"

    brand_code = fields.Char(required=True, index=True)
    brand_name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True)
    product_category_ids = fields.Many2many("product.category")
    royalty_pct = fields.Float(digits=(6, 4))
    effective_from = fields.Date(required=True, default=fields.Date.context_today)
    effective_to = fields.Date()
    active = fields.Boolean(default=True)
    note = fields.Text()

    _sql_constraints = [
        (
            "uniq_brand_company_period",
            "unique(brand_code, company_id, effective_from)",
            "Duplicate license for this brand / company / start date.",
        ),
    ]

    @api.model
    def is_company_licensed(self, company, brand_code, on_date=None):
        on_date = on_date or fields.Date.context_today(self)
        return bool(self.search([
            ("brand_code", "=", brand_code),
            ("company_id", "=", company.id),
            ("active", "=", True),
            ("effective_from", "<=", on_date),
            "|", ("effective_to", "=", False), ("effective_to", ">=", on_date),
        ], limit=1))

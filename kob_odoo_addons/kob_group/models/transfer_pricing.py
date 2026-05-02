# -*- coding: utf-8 -*-
"""Transfer pricing agreement — A→B intercompany invoice price rule."""

from odoo import api, fields, models, _


class KobTransferPricingAgreement(models.Model):
    _name = "kob.transfer.pricing.agreement"
    _description = "Transfer Pricing Agreement"
    _order = "from_company_id, to_company_id"

    name = fields.Char(required=True)
    from_company_id = fields.Many2one("res.company", required=True)
    to_company_id = fields.Many2one("res.company", required=True)
    product_category_id = fields.Many2one(
        "product.category",
        help="Leave empty for ALL categories.",
    )
    method = fields.Selection(
        [
            ("cost_plus", "Cost-plus"),
            ("list_price", "List price"),
            ("manual", "Manual"),
        ],
        default="cost_plus",
        required=True,
    )
    markup_pct = fields.Float(digits=(6, 4))
    effective_from = fields.Date(required=True, default=fields.Date.context_today)
    effective_to = fields.Date()
    active = fields.Boolean(default=True)
    note = fields.Text()

    _sql_constraints = [
        (
            "uniq_pair_category_period",
            "unique(from_company_id, to_company_id, product_category_id, effective_from)",
            "Duplicate agreement for this pair / category / start date.",
        ),
    ]

    @api.model
    def lookup(self, from_company, to_company, product_category=None,
               on_date=None):
        """Find the most-specific active agreement for a pair on a date."""
        on_date = on_date or fields.Date.context_today(self)
        domain = [
            ("from_company_id", "=", from_company.id),
            ("to_company_id", "=", to_company.id),
            ("active", "=", True),
            ("effective_from", "<=", on_date),
            "|", ("effective_to", "=", False), ("effective_to", ">=", on_date),
        ]
        # Prefer category-specific over general
        if product_category:
            specific = self.search(
                domain + [("product_category_id", "=", product_category.id)],
                limit=1,
            )
            if specific:
                return specific
        return self.search(
            domain + [("product_category_id", "=", False)],
            limit=1,
        )

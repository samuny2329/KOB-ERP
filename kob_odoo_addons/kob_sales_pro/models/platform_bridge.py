# -*- coding: utf-8 -*-
"""Bridge: one sale.order ↔ many marketplace platform orders.

Each row records the per-platform commission/subsidy KOB pays
(Shopee/Lazada/TikTok) for the share of revenue that came through that
platform on a given Odoo SO.
"""

from odoo import api, fields, models


class KobPlatformOrderBridge(models.Model):
    _name = "kob.platform.order.bridge"
    _description = "SO ↔ Platform Order Bridge"
    _order = "sale_order_id, id"

    _sql_constraints = [
        (
            "uniq_pair",
            "unique(sale_order_id, platform, platform_order_ref)",
            "This platform order is already bridged to this SO.",
        ),
    ]

    sale_order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade", index=True,
    )
    platform = fields.Selection(
        [
            ("shopee", "Shopee"),
            ("lazada", "Lazada"),
            ("tiktok", "TikTok"),
            ("other", "Other"),
        ],
        required=True,
    )
    platform_order_ref = fields.Char(
        string="Platform Order #",
        help="The platform's own order ID (e.g. Shopee order_sn).",
    )
    commission_pct = fields.Float(digits=(6, 2))
    commission_deducted = fields.Monetary(currency_field="currency_id")
    shipping_subsidy = fields.Monetary(currency_field="currency_id")
    note = fields.Char()
    currency_id = fields.Many2one(
        related="sale_order_id.currency_id", store=True, readonly=True,
    )

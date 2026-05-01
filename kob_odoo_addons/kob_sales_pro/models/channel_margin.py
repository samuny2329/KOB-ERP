# -*- coding: utf-8 -*-
"""Channel margin snapshot — refreshable per (channel, period)."""

from datetime import timedelta

from odoo import api, fields, models, _


class KobChannelMargin(models.Model):
    _name = "kob.channel.margin"
    _description = "Channel Margin Snapshot"
    _order = "period_start desc, channel"
    _sql_constraints = [
        (
            "uniq_company_channel_period",
            "unique(company_id, channel, period_start)",
            "Snapshot already exists for this channel and period.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    channel = fields.Selection(
        [
            ("shopee", "Shopee"),
            ("lazada", "Lazada"),
            ("tiktok", "TikTok"),
            ("offline", "Offline"),
            ("website", "Website"),
            ("other", "Other"),
        ],
        required=True,
    )
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    gross_revenue = fields.Monetary(currency_field="currency_id")
    cogs = fields.Monetary(currency_field="currency_id")
    platform_fees = fields.Monetary(currency_field="currency_id")
    shipping_cost = fields.Monetary(currency_field="currency_id")
    return_amount = fields.Monetary(currency_field="currency_id")
    net_margin = fields.Monetary(currency_field="currency_id")
    margin_pct = fields.Float(digits=(5, 2))
    order_count = fields.Integer()
    refreshed_at = fields.Datetime(readonly=True)

    @api.model
    def refresh_period(self, channel, period_start, period_end, company=None):
        """Recompute one (channel, period) snapshot for current company."""
        company = company or self.env.company
        domain = [
            ("state", "in", ("sale", "done")),
            ("date_order", ">=", fields.Datetime.to_string(period_start)),
            ("date_order", "<=", fields.Datetime.to_string(period_end)),
            ("company_id", "=", company.id),
        ]
        SO = self.env["sale.order"]
        orders = SO.search(domain)
        if channel in ("shopee", "lazada", "tiktok"):
            orders = orders.filtered(
                lambda so: any(
                    b.platform == channel for b in so.platform_bridge_ids
                ),
            )
        bridges = self.env["kob.platform.order.bridge"].search([
            ("sale_order_id", "in", orders.ids),
            ("platform", "=", channel),
        ])
        gross = sum(orders.mapped("amount_total"))
        # Approximate COGS from order lines product cost
        cogs = 0.0
        for line in orders.mapped("order_line"):
            cogs += float(line.product_id.standard_price or 0) * float(
                line.product_uom_qty or 0,
            )
        platform_fees = sum(bridges.mapped("commission_deducted"))
        shipping = sum(bridges.mapped("shipping_subsidy"))
        # Returns
        Returns = self.env["kob.return.order"]
        returns = Returns.search([
            ("sales_order_id", "in", orders.ids),
            ("state", "in", ("restocked", "scrapped")),
        ])
        return_amount = sum(returns.mapped("refund_amount"))

        net = gross - cogs - platform_fees - shipping - return_amount
        margin_pct = (
            round((net / gross) * 100.0, 2) if gross else 0.0
        )

        existing = self.search([
            ("company_id", "=", company.id),
            ("channel", "=", channel),
            ("period_start", "=", period_start),
        ], limit=1)
        vals = {
            "company_id": company.id,
            "channel": channel,
            "period_start": period_start,
            "period_end": period_end,
            "gross_revenue": gross,
            "cogs": cogs,
            "platform_fees": platform_fees,
            "shipping_cost": shipping,
            "return_amount": return_amount,
            "net_margin": net,
            "margin_pct": margin_pct,
            "order_count": len(orders),
            "refreshed_at": fields.Datetime.now(),
        }
        if existing:
            existing.write(vals)
            return existing
        return self.create(vals)

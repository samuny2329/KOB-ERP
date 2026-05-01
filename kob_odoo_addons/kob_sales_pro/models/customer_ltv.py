# -*- coding: utf-8 -*-
"""Customer LTV (Lifetime Value) snapshots — append-only 90-day spend."""

from datetime import timedelta

from odoo import api, fields, models, _


class KobCustomerLtvSnapshot(models.Model):
    _name = "kob.customer.ltv.snapshot"
    _description = "Customer LTV Snapshot"
    _order = "snapshot_date desc, partner_id"

    partner_id = fields.Many2one(
        "res.partner", required=True, ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    snapshot_date = fields.Date(
        required=True, default=fields.Date.context_today,
    )
    revenue_90d = fields.Monetary(currency_field="currency_id")
    avg_order_value = fields.Monetary(currency_field="currency_id")
    order_count_90d = fields.Integer()
    repeat_rate = fields.Float(digits=(5, 2))
    return_rate = fields.Float(digits=(5, 2))
    score = fields.Float(digits=(14, 2))
    breakdown = fields.Char()

    @api.model
    def refresh_for(self, partner):
        """Compute one snapshot for `partner` based on last 90 days."""
        end = fields.Date.context_today(self)
        start = end - timedelta(days=90)
        SO = self.env["sale.order"]
        orders = SO.search([
            ("partner_id", "=", partner.id),
            ("state", "in", ("sale", "done")),
            ("date_order", ">=", fields.Datetime.to_string(start)),
            ("date_order", "<=", fields.Datetime.to_string(end)),
        ])
        revenue_90d = sum(orders.mapped("amount_total"))
        order_count = len(orders)
        aov = (revenue_90d / order_count) if order_count else 0.0

        # Returns: link via kob.return.order on the SOs
        Returns = self.env["kob.return.order"]
        returns = Returns.search([
            ("sales_order_id", "in", orders.ids),
            ("state", "in", ("restocked", "scrapped")),
        ])
        refund_total = sum(returns.mapped("refund_amount"))
        return_rate = (
            round((refund_total / revenue_90d) * 100.0, 2)
            if revenue_90d else 0.0
        )
        repeat_rate = (
            100.0 if order_count >= 2
            else (50.0 if order_count == 1 else 0.0)
        )
        # LTV score = revenue × repeat × (1 - return) — scaled by 100 inputs
        score = round(
            float(revenue_90d) * (repeat_rate / 100.0)
            * (1.0 - return_rate / 100.0),
            2,
        )
        snap = self.create({
            "partner_id": partner.id,
            "snapshot_date": end,
            "revenue_90d": revenue_90d,
            "avg_order_value": round(aov, 2),
            "order_count_90d": order_count,
            "repeat_rate": repeat_rate,
            "return_rate": return_rate,
            "score": score,
            "breakdown": "orders=%d refund_total=%s window=%s..%s" % (
                order_count, float(refund_total), start, end,
            ),
        })
        partner.ltv_score = score
        return snap

    @api.model
    def _cron_refresh_active_customers(self):
        """Daily — recompute LTV for customers with sales in the last 90 days."""
        cutoff = fields.Datetime.now() - timedelta(days=90)
        partners = self.env["sale.order"].search([
            ("state", "in", ("sale", "done")),
            ("date_order", ">=", cutoff),
        ]).mapped("partner_id")
        for p in partners:
            self.refresh_for(p)

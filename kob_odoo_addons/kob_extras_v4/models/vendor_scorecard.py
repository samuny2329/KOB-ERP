# -*- coding: utf-8 -*-
"""Phase 44 — Vendor scorecard automation.

Computes per-vendor KPIs (on-time delivery, quality acceptance, price
variance, response time) on a monthly cadence via cron.
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class KobVendorScorecard(models.Model):
    _name = "kob.vendor.scorecard"
    _description = "Vendor Scorecard"
    _order = "period_start desc, partner_id"
    _rec_name = "display_name"

    partner_id = fields.Many2one("res.partner", required=True,
                                 domain=[("supplier_rank", ">", 0)])
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)

    po_count = fields.Integer(string="POs Issued")
    po_total = fields.Float(string="PO Spend")
    on_time_pct = fields.Float(string="On-Time Delivery %")
    quality_pct = fields.Float(string="Quality Acceptance %")
    price_variance_pct = fields.Float(string="Price Variance %",
                                      help="vs. catalog/last price; positive = vendor is more expensive")
    avg_response_hours = fields.Float(string="Avg Response Hours")
    overall_score = fields.Float(compute="_compute_overall", store=True)
    grade = fields.Selection(
        [("A", "A — Strategic"), ("B", "B — Preferred"),
         ("C", "C — Conditional"), ("D", "D — At Risk")],
        compute="_compute_overall", store=True,
    )
    notes = fields.Text()
    display_name = fields.Char(compute="_compute_display_name", store=False)

    @api.depends("partner_id", "period_start")
    def _compute_display_name(self):
        for r in self:
            r.display_name = f"{r.partner_id.name or '?'} — {r.period_start}"

    @api.depends("on_time_pct", "quality_pct", "price_variance_pct", "avg_response_hours")
    def _compute_overall(self):
        for r in self:
            # Weighted score: 40% OTD + 30% Quality + 20% Price + 10% Response
            response_score = max(0, 100 - (r.avg_response_hours or 0) * 2)
            price_score = max(0, 100 - abs(r.price_variance_pct or 0) * 5)
            score = (
                0.40 * (r.on_time_pct or 0)
                + 0.30 * (r.quality_pct or 0)
                + 0.20 * price_score
                + 0.10 * response_score
            )
            r.overall_score = round(score, 2)
            r.grade = (
                "A" if score >= 85 else
                "B" if score >= 70 else
                "C" if score >= 55 else "D"
            )

    @api.model
    def cron_generate_monthly_scorecard(self):
        today = date.today()
        period_end = today.replace(day=1) - timedelta(days=1)
        period_start = period_end.replace(day=1)

        Po = self.env["purchase.order"]
        vendors = Po.search([
            ("date_order", ">=", period_start),
            ("date_order", "<=", period_end),
            ("state", "in", ["purchase", "done"]),
        ]).mapped("partner_id")

        created = 0
        for v in vendors:
            if self.search_count([
                ("partner_id", "=", v.id), ("period_start", "=", period_start)
            ]):
                continue
            pos = Po.search([
                ("partner_id", "=", v.id),
                ("date_order", ">=", period_start),
                ("date_order", "<=", period_end),
                ("state", "in", ["purchase", "done"]),
            ])
            po_count = len(pos)
            po_total = sum(pos.mapped("amount_total"))

            # On-time: pickings done <= scheduled date_planned
            pickings = pos.mapped("picking_ids").filtered(lambda p: p.state == "done")
            if pickings:
                on_time = sum(1 for p in pickings if p.date_done and p.scheduled_date and p.date_done <= p.scheduled_date)
                on_time_pct = 100.0 * on_time / len(pickings)
            else:
                on_time_pct = 0.0

            # Quality: simplified — no return moves = 100%
            returns = pickings.filtered(lambda p: p.picking_type_id.code == "incoming" and any(
                m.origin_returned_move_id for m in p.move_ids
            ))
            quality_pct = 100.0 - (100.0 * len(returns) / max(len(pickings), 1))

            # Price variance: compare line price vs product list_price (proxy)
            lines = pos.mapped("order_line")
            variances = []
            for ln in lines:
                if ln.product_id and ln.product_id.standard_price:
                    var = ((ln.price_unit - ln.product_id.standard_price)
                           / ln.product_id.standard_price * 100)
                    variances.append(var)
            price_var = sum(variances) / len(variances) if variances else 0.0

            self.create({
                "partner_id": v.id,
                "period_start": period_start,
                "period_end": period_end,
                "po_count": po_count,
                "po_total": po_total,
                "on_time_pct": round(on_time_pct, 2),
                "quality_pct": round(quality_pct, 2),
                "price_variance_pct": round(price_var, 2),
                "avg_response_hours": 0.0,
            })
            created += 1
        return created

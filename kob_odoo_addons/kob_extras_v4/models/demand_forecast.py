# -*- coding: utf-8 -*-
"""Phase 43 — Forecast + demand planning.

Per-product monthly forecast computed from rolling 90/180-day sales velocity
with simple seasonal multiplier. Meant as a baseline; can be edited by planner.
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class KobDemandForecast(models.Model):
    _name = "kob.demand.forecast"
    _description = "Demand Forecast"
    _order = "period_start desc, product_id"
    _rec_name = "display_name"

    product_id = fields.Many2one("product.product", required=True, ondelete="cascade")
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    horizon_months = fields.Integer(default=1)
    baseline_qty = fields.Float(string="Baseline Qty",
                                help="Auto-computed from sales velocity")
    seasonal_factor = fields.Float(default=1.0)
    forecast_qty = fields.Float(compute="_compute_forecast", store=True)
    actual_qty = fields.Float(string="Actual Sold", compute="_compute_actual", store=False)
    accuracy_pct = fields.Float(compute="_compute_actual", store=False)
    notes = fields.Text()
    display_name = fields.Char(compute="_compute_display_name", store=False)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)

    @api.depends("product_id", "period_start")
    def _compute_display_name(self):
        for r in self:
            r.display_name = f"{r.product_id.display_name or '?'} — {r.period_start}"

    @api.depends("baseline_qty", "seasonal_factor")
    def _compute_forecast(self):
        for r in self:
            r.forecast_qty = (r.baseline_qty or 0.0) * (r.seasonal_factor or 1.0)

    def _compute_actual(self):
        SaleLine = self.env["sale.order.line"]
        for r in self:
            lines = SaleLine.search([
                ("product_id", "=", r.product_id.id),
                ("order_id.date_order", ">=", r.period_start),
                ("order_id.date_order", "<=", r.period_end),
                ("order_id.state", "in", ["sale", "done"]),
            ])
            r.actual_qty = sum(lines.mapped("product_uom_qty"))
            r.accuracy_pct = (
                100.0 * (1 - abs(r.forecast_qty - r.actual_qty) / r.forecast_qty)
                if r.forecast_qty else 0.0
            )

    @api.model
    def cron_generate_monthly_forecast(self):
        """Generate next-month forecast for all storable products."""
        today = date.today()
        period_start = (today + relativedelta(day=1, months=1))
        period_end = period_start + relativedelta(months=1, days=-1)
        velocity_start = today - timedelta(days=90)

        products = self.env["product.product"].search([("type", "=", "consu"), ("sale_ok", "=", True)])
        SaleLine = self.env["sale.order.line"]
        created = 0
        for p in products:
            if self.search_count([
                ("product_id", "=", p.id), ("period_start", "=", period_start)
            ]):
                continue
            lines = SaleLine.search([
                ("product_id", "=", p.id),
                ("order_id.date_order", ">=", velocity_start),
                ("order_id.state", "in", ["sale", "done"]),
            ])
            qty_90d = sum(lines.mapped("product_uom_qty"))
            baseline = (qty_90d / 3.0) if qty_90d else 0.0
            self.create({
                "product_id": p.id,
                "period_start": period_start,
                "period_end": period_end,
                "horizon_months": 1,
                "baseline_qty": baseline,
                "seasonal_factor": 1.0,
            })
            created += 1
        return created

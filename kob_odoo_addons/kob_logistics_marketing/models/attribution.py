# -*- coding: utf-8 -*-
"""Phase 54 — Attribution / ROI dashboard.

Records every marketing touchpoint (email open, sms send, ads click,
referral) and links them to eventual orders via UTM tags + customer hash.
"""
from datetime import date, timedelta

from odoo import api, fields, models


class KobMarketingTouch(models.Model):
    _name = "kob.marketing.touch"
    _description = "Marketing Touchpoint"
    _order = "touch_at desc"

    partner_id = fields.Many2one("res.partner")
    channel = fields.Selection(
        [("email", "Email"),
         ("sms", "SMS"),
         ("organic", "Organic Search"),
         ("paid_search", "Paid Search"),
         ("social_paid", "Social Ads"),
         ("social_organic", "Social Organic"),
         ("affiliate", "Affiliate"),
         ("referral", "Referral"),
         ("direct", "Direct"),
         ("other", "Other")],
        required=True,
    )
    campaign_id = fields.Many2one("utm.campaign")
    source = fields.Char()
    medium = fields.Char()
    term = fields.Char()
    content = fields.Char()
    cost = fields.Float(help="Allocated cost for this touch")
    touch_at = fields.Datetime(default=fields.Datetime.now, required=True,
                               index=True)
    converted = fields.Boolean(default=False)
    conversion_order_id = fields.Many2one("sale.order")
    conversion_value = fields.Float()


class KobAttributionReport(models.Model):
    _name = "kob.attribution.report"
    _description = "Attribution Report"
    _order = "period_start desc, channel"
    _rec_name = "display_name"

    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    channel = fields.Char(required=True)
    touch_count = fields.Integer()
    conversion_count = fields.Integer()
    conversion_rate = fields.Float(compute="_compute_kpis", store=True)
    cost = fields.Float()
    revenue = fields.Float()
    roi_pct = fields.Float(compute="_compute_kpis", store=True,
                           help="(revenue - cost) / cost * 100")
    cac = fields.Float(string="CAC", compute="_compute_kpis", store=True,
                       help="Customer Acquisition Cost = cost / conversions")
    display_name = fields.Char(compute="_compute_display_name", store=False)

    @api.depends("period_start", "channel")
    def _compute_display_name(self):
        for r in self:
            r.display_name = f"{r.channel} — {r.period_start}"

    @api.depends("touch_count", "conversion_count", "cost", "revenue")
    def _compute_kpis(self):
        for r in self:
            r.conversion_rate = (100.0 * r.conversion_count / r.touch_count
                                 if r.touch_count else 0)
            r.roi_pct = ((r.revenue - r.cost) / r.cost * 100
                         if r.cost else 0)
            r.cac = (r.cost / r.conversion_count
                     if r.conversion_count else 0)

    @api.model
    def cron_compute_monthly(self):
        today = date.today()
        period_end = today.replace(day=1) - timedelta(days=1)
        period_start = period_end.replace(day=1)
        Touch = self.env["kob.marketing.touch"]
        channels = list(set(Touch.search([
            ("touch_at", ">=", period_start),
            ("touch_at", "<=", period_end),
        ]).mapped("channel")))
        created = 0
        for ch in channels:
            if self.search_count([
                ("period_start", "=", period_start),
                ("channel", "=", ch)
            ]):
                continue
            touches = Touch.search([
                ("touch_at", ">=", period_start),
                ("touch_at", "<=", period_end),
                ("channel", "=", ch),
            ])
            self.create({
                "period_start": period_start,
                "period_end": period_end,
                "channel": ch,
                "touch_count": len(touches),
                "conversion_count": len(touches.filtered("converted")),
                "cost": sum(touches.mapped("cost")),
                "revenue": sum(touches.mapped("conversion_value")),
            })
            created += 1
        return created

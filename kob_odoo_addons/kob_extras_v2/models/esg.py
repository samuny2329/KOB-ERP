# -*- coding: utf-8 -*-
"""Phase 32 — ESG / Sustainability metrics."""
from odoo import api, fields, models


class KobEsgMetric(models.Model):
    _name = "kob.esg.metric"
    _description = "ESG Metric"
    _order = "period_year desc, period_month desc"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    metric_type = fields.Selection(
        [
            ("carbon_kgco2", "Carbon (kg CO₂e)"),
            ("water_m3", "Water (m³)"),
            ("waste_kg", "Waste (kg)"),
            ("energy_kwh", "Energy (kWh)"),
            ("paper_sheets", "Paper (sheets)"),
            ("plastic_kg", "Plastic Used (kg)"),
            ("recycled_kg", "Recycled (kg)"),
            ("renewable_pct", "Renewable Energy %"),
        ],
        required=True,
    )
    value = fields.Float(required=True)
    target = fields.Float(help="Target/budget for this period")
    variance_pct = fields.Float(compute="_compute_variance", store=True)
    note = fields.Text()

    @api.depends("metric_type", "period_year", "period_month")
    def _compute_name(self):
        for r in self:
            r.name = f"{r.metric_type or '?'}/{r.period_year}/{r.period_month:02d}"

    @api.depends("value", "target")
    def _compute_variance(self):
        for r in self:
            r.variance_pct = (
                ((r.value - r.target) / r.target * 100.0)
                if r.target else 0.0
            )

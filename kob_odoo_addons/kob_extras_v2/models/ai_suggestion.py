# -*- coding: utf-8 -*-
"""Phase 33 — AI Suggestion placeholder.

Records auto-generated suggestions:
  - "Reorder X — stock < safety"
  - "Customer Y churning — last order > 60d"
  - "Vendor Z late — on-time < 80%"

Actual ML inference can be wired later via API call.
"""
from odoo import api, fields, models


class KobAiSuggestion(models.Model):
    _name = "kob.ai.suggestion"
    _description = "AI Suggestion"
    _order = "priority desc, create_date desc"

    title = fields.Char(required=True)
    category = fields.Selection(
        [
            ("reorder", "Reorder Suggestion"),
            ("churn", "Customer Churn Risk"),
            ("vendor", "Vendor Performance Alert"),
            ("anomaly", "Anomaly Detected"),
            ("forecast", "Demand Forecast"),
            ("price", "Pricing Suggestion"),
            ("other", "Other"),
        ],
        default="other",
    )
    priority = fields.Selection(
        [("0", "Low"), ("1", "Medium"), ("2", "High"), ("3", "Critical")],
        default="1",
    )
    message = fields.Text()
    related_model = fields.Char()
    related_id = fields.Integer()
    confidence_pct = fields.Float(help="ML model confidence 0-100")
    state = fields.Selection(
        [
            ("new", "New"),
            ("acknowledged", "Acknowledged"),
            ("acted", "Acted On"),
            ("dismissed", "Dismissed"),
        ],
        default="new",
    )
    create_date = fields.Datetime(readonly=True)

    def action_acknowledge(self):
        for r in self:
            r.state = "acknowledged"

    def action_dismiss(self):
        for r in self:
            r.state = "dismissed"

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
    """Extends the canonical ``kob.ai.suggestion`` model (defined in
    ``kob_ai_agent``) with ML-classification fields.

    Was originally defined with `_name`, which caused a duplicate-class
    conflict with kob_ai_agent: the action with domain
    ``[('status','=','pending')]`` failed because libsass / ORM only saw
    the kob_extras_v2 fields (state/category) and not kob_ai_agent's
    ``status``. Switched to `_inherit` so both field sets coexist on one
    table.
    """
    _inherit = "kob.ai.suggestion"

    title = fields.Char()  # not required when inheriting
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

    def action_acknowledge(self):
        for r in self:
            r.state = "acknowledged"

    def action_dismiss(self):
        for r in self:
            r.state = "dismissed"

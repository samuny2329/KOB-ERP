# -*- coding: utf-8 -*-
"""FX revaluation snapshot per (company, currency, period).

Ported from ``backend/modules/accounting/models_advanced.py``
(``FxRevaluation``).

Translates monetary balances at period-end rate vs the booked rate;
the difference is recognised as FX gain or loss in the same period.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobFxRevaluation(models.Model):
    _name = "kob.fx.revaluation"
    _description = "FX Revaluation"
    _order = "period_year desc, period_month desc, currency"
    _sql_constraints = [
        (
            "uniq_fx_revaluation",
            "unique(company_id, currency, period_year, period_month)",
            "FX revaluation already exists for this company/currency/month.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
        index=True,
    )
    currency = fields.Char(
        string="FC Currency",
        required=True,
        size=10,
        help="ISO 4217 code, e.g. USD, EUR, JPY.",
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    period_end_rate = fields.Float(
        digits=(14, 6), required=True,
        help="Closing rate FC→THB on the last day of the period.",
    )
    booked_balance_fc = fields.Float(
        digits=(18, 2), required=True,
        help="Balance in foreign currency before revaluation.",
    )
    booked_balance_thb = fields.Float(
        digits=(18, 2), required=True,
        help="Balance in THB at the originally booked rates.",
    )
    revalued_balance_thb = fields.Float(digits=(18, 2), required=True)
    fx_gain_loss = fields.Float(
        digits=(18, 2), default=0, readonly=True,
        help="Positive = gain, negative = loss. Auto-computed from "
             "(revalued − booked).",
    )
    posted_at = fields.Datetime()
    move_id = fields.Many2one(
        "account.move", string="Journal Entry", ondelete="set null",
    )
    note = fields.Text()

    @api.onchange(
        "booked_balance_fc", "period_end_rate",
        "booked_balance_thb",
    )
    def _onchange_compute(self):
        for rec in self:
            if rec.booked_balance_fc and rec.period_end_rate:
                rec.revalued_balance_thb = round(
                    float(rec.booked_balance_fc)
                    * float(rec.period_end_rate),
                    2,
                )
            if rec.revalued_balance_thb and rec.booked_balance_thb is not None:
                rec.fx_gain_loss = round(
                    float(rec.revalued_balance_thb)
                    - float(rec.booked_balance_thb),
                    2,
                )

    @api.model_create_multi
    def create(self, vals_list):
        # Ensure fx_gain_loss is computed even when bypassing onchange
        # (CSV import, API).
        for vals in vals_list:
            try:
                rev = float(vals.get("revalued_balance_thb", 0))
                book = float(vals.get("booked_balance_thb", 0))
                vals.setdefault("fx_gain_loss", round(rev - book, 2))
            except (TypeError, ValueError):
                pass
        return super().create(vals_list)

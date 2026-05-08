# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MeaFtPeriod(models.Model):
    _name = "mea.ft.period"
    _description = "MEA Ft (Fuel Tariff Adjustment) Period"
    _order = "period_start desc"

    name = fields.Char(
        compute="_compute_name", store=True,
        help="Auto-computed display label (period range + rate).",
    )
    period_start = fields.Date(
        required=True, index=True,
        help="First day this Ft rate applies. Quarterly cycles published by ERC.",
    )
    period_end = fields.Date(
        required=True,
        help="Last day this Ft rate applies. Periods must not overlap.",
    )
    ft_rate = fields.Float(
        string="Ft Rate (stang/kWh)", digits=(8, 4),
        help="Retail Ft (Fuel Tariff Adjustment) published by ERC quarterly. "
             "Stored in satang per kWh (e.g. 9.72 = 0.0972 THB/kWh). "
             "Calculator divides by 100 to get THB/kWh for cost computation.",
    )
    change_satang = fields.Float(
        string="Change vs Previous (stang)", digits=(8, 4),
        help="Delta in satang compared to previous Ft period. "
             "Positive = increase, negative = decrease. Useful for trend tracking.",
    )
    published_date = fields.Date(
        help="Date ERC officially published this Ft rate.",
    )
    source_url = fields.Char(
        help="Link to ERC announcement or news release for verification.",
    )
    note = fields.Text(
        help="Free-text notes (e.g. exceptional one-time adjustments, "
             "claw-back mechanism details).",
    )

    @api.depends("period_start", "period_end", "ft_rate")
    def _compute_name(self):
        for r in self:
            if r.period_start and r.period_end:
                r.name = f"{r.period_start.strftime('%Y-%m')} → {r.period_end.strftime('%Y-%m')} ({r.ft_rate:.2f}st)"
            else:
                r.name = "Ft Period"

    @api.constrains("period_start", "period_end")
    def _check_range(self):
        for r in self:
            if r.period_end < r.period_start:
                raise ValidationError("period_end must be >= period_start.")
            overlap = self.search([
                ("id", "!=", r.id),
                ("period_start", "<=", r.period_end),
                ("period_end", ">=", r.period_start),
            ], limit=1)
            if overlap:
                raise ValidationError(
                    f"Ft period overlaps with existing record '{overlap.name}'."
                )

    @api.model
    def get_for_date(self, target_date):
        """Return the Ft period covering ``target_date`` or empty recordset."""
        if not target_date:
            return self.browse()
        return self.search([
            ("period_start", "<=", target_date),
            ("period_end", ">=", target_date),
        ], limit=1)

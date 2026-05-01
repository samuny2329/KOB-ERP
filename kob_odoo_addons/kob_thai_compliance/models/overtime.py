# -*- coding: utf-8 -*-
"""Overtime record (Thai LPA multipliers)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .services import compute_overtime, OT_MULTIPLIERS


class KobOvertimeRecord(models.Model):
    _name = "kob.overtime.record"
    _description = "Overtime Record (Thai LPA)"
    _order = "work_date desc, employee_id"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    employee_id = fields.Many2one(
        "hr.employee", required=True, ondelete="cascade", index=True,
    )
    work_date = fields.Date(required=True, default=fields.Date.context_today)
    ot_kind = fields.Selection(
        [
            ("weekday_after_hours", "Weekday After Hours (×1.5)"),
            ("weekend_normal", "Weekend Normal Hours (×1.0)"),
            ("weekend_after_hours", "Weekend After Hours (×3.0)"),
            ("holiday", "Holiday (×3.0)"),
        ],
        required=True,
        default="weekday_after_hours",
    )
    hours = fields.Float(required=True)
    base_hourly_rate = fields.Monetary(required=True, currency_field="currency_id")
    rate_multiplier = fields.Float(
        compute="_compute_total", store=True, readonly=True,
    )
    total_amount = fields.Monetary(
        compute="_compute_total", store=True, currency_field="currency_id",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    note = fields.Text()
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )

    @api.depends("ot_kind", "hours", "base_hourly_rate")
    def _compute_total(self):
        for rec in self:
            if not rec.ot_kind or rec.hours <= 0 or rec.base_hourly_rate <= 0:
                rec.rate_multiplier = OT_MULTIPLIERS.get(rec.ot_kind or "", 0.0)
                rec.total_amount = 0.0
                continue
            try:
                total, mult = compute_overtime(
                    rec.ot_kind, rec.hours, rec.base_hourly_rate
                )
            except KeyError as exc:
                raise UserError(_("Unknown OT kind: %s") % exc.args[0])
            rec.rate_multiplier = mult
            rec.total_amount = total

    def action_approve(self):
        self.filtered(lambda r: r.state == "draft").write({"state": "approved"})

    def action_pay(self):
        self.filtered(lambda r: r.state == "approved").write({"state": "paid"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

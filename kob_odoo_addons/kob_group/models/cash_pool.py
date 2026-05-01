# -*- coding: utf-8 -*-
"""Cash pool — group treasury aggregation across bank accounts."""

from odoo import api, fields, models


class KobCashPool(models.Model):
    _name = "kob.cash.pool"
    _description = "Cash Pool"
    _order = "name"

    name = fields.Char(required=True)
    parent_company_id = fields.Many2one("res.company", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda s: s.env.company.currency_id,
    )
    member_ids = fields.One2many("kob.cash.pool.member", "pool_id")
    forecast_ids = fields.One2many("kob.cash.forecast.snapshot", "pool_id")
    target_balance = fields.Monetary(currency_field="currency_id")
    note = fields.Text()
    active = fields.Boolean(default=True)


class KobCashPoolMember(models.Model):
    _name = "kob.cash.pool.member"
    _description = "Cash Pool Member"

    pool_id = fields.Many2one(
        "kob.cash.pool", required=True, ondelete="cascade",
    )
    company_id = fields.Many2one("res.company", required=True)
    bank_journal_id = fields.Many2one(
        "account.journal",
        domain=[("type", "in", ("bank", "cash"))],
    )
    weight = fields.Float(digits=(6, 4), default=1.0)


class KobCashForecastSnapshot(models.Model):
    _name = "kob.cash.forecast.snapshot"
    _description = "Cash Forecast Snapshot"
    _order = "forecast_date desc"

    pool_id = fields.Many2one("kob.cash.pool", ondelete="cascade")
    company_id = fields.Many2one("res.company")
    forecast_date = fields.Date(required=True)
    horizon_days = fields.Integer(default=30)
    opening_balance = fields.Monetary(currency_field="currency_id")
    cash_in = fields.Monetary(currency_field="currency_id")
    cash_out = fields.Monetary(currency_field="currency_id")
    projected_balance = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_projected", store=True,
    )
    target_balance = fields.Monetary(currency_field="currency_id")
    risk_flag = fields.Selection(
        [
            ("ok", "OK"),
            ("low", "Low"),
            ("critical", "Critical"),
        ],
        compute="_compute_projected", store=True,
    )
    breakdown = fields.Char()
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda s: s.env.company.currency_id,
    )

    @api.depends(
        "opening_balance", "cash_in", "cash_out",
        "target_balance",
    )
    def _compute_projected(self):
        for rec in self:
            proj = (
                float(rec.opening_balance or 0)
                + float(rec.cash_in or 0)
                - float(rec.cash_out or 0)
            )
            rec.projected_balance = proj
            target = float(rec.target_balance or 0)
            if target <= 0:
                rec.risk_flag = "ok"
            elif proj >= target:
                rec.risk_flag = "ok"
            elif proj >= target * 0.8:
                rec.risk_flag = "low"
            else:
                rec.risk_flag = "critical"

# -*- coding: utf-8 -*-
"""Fixed asset register + depreciation schedule.

Ported from ``backend/modules/accounting/models_advanced.py``
(``FixedAsset`` + ``DepreciationEntry``).

Methods:
  * straight_line     — equal depreciation over useful life
  * declining_balance — 2× straight-line rate applied to book value
  * units_of_production — usage-driven (rate × units used; manual entry)
"""

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobFixedAsset(models.Model):
    _name = "kob.fixed.asset"
    _description = "Fixed Asset"
    _order = "asset_code"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    asset_code = fields.Char(required=True, copy=False, index=True)
    name = fields.Char(required=True)
    category = fields.Char()
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_use", "In use"),
            ("fully_depreciated", "Fully depreciated"),
            ("disposed", "Disposed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        tracking=True,
    )
    acquisition_date = fields.Date(required=True, default=fields.Date.context_today)
    acquisition_cost = fields.Monetary(currency_field="currency_id", required=True)
    salvage_value = fields.Monetary(currency_field="currency_id", default=0)
    depreciation_method = fields.Selection(
        [
            ("straight_line", "Straight-line"),
            ("declining_balance", "Declining balance (2×)"),
            ("units_of_production", "Units of production"),
        ],
        default="straight_line",
        required=True,
    )
    useful_life_months = fields.Integer(
        required=True, default=60,
        help="60 = 5 years (typical for office equipment).",
    )
    accumulated_depreciation = fields.Monetary(
        currency_field="currency_id", readonly=True,
    )
    book_value = fields.Monetary(currency_field="currency_id", readonly=True)

    # Account links — optional, used when posting depreciation JEs.
    asset_account_id = fields.Many2one(
        "account.account", string="Asset Account",
        domain="[('account_type', 'in', ['asset_fixed', 'asset_non_current'])]",
    )
    accumulated_depreciation_account_id = fields.Many2one(
        "account.account", string="Accum. Depr. Account",
        domain="[('account_type', 'in', ['asset_fixed', 'asset_non_current'])]",
    )
    depreciation_expense_account_id = fields.Many2one(
        "account.account", string="Depr. Expense Account",
        domain="[('account_type', '=', 'expense_depreciation')]",
    )

    location = fields.Char()
    custodian_employee_id = fields.Many2one("hr.employee", string="Custodian")
    disposal_date = fields.Date()
    disposal_proceeds = fields.Monetary(currency_field="currency_id")
    note = fields.Text()
    schedule_ids = fields.One2many(
        "kob.depreciation.entry", "asset_id", string="Depreciation Schedule",
    )

    _sql_constraints = [
        ("uniq_asset_code", "unique(asset_code)", "Asset code must be unique."),
    ]

    def action_activate(self):
        """Move pending → in_use and generate full schedule."""
        for asset in self:
            if asset.state != "pending":
                raise UserError(_("Only pending assets can be activated."))
            asset._generate_schedule()
            asset.state = "in_use"
            asset.book_value = float(asset.acquisition_cost) - float(
                asset.accumulated_depreciation or 0,
            )

    def action_dispose(self):
        for asset in self:
            if asset.state != "in_use":
                raise UserError(_("Only in-use assets can be disposed."))
            asset.write({
                "state": "disposed",
                "disposal_date": fields.Date.context_today(asset),
            })

    def action_cancel(self):
        for asset in self:
            if asset.state != "pending":
                raise UserError(_("Only pending assets can be cancelled."))
            asset.state = "cancelled"

    def _generate_schedule(self):
        """Compute (period_year, period_month, amount) entries.

        For straight-line: equal depreciation per month over useful life.
        For declining-balance: 2 × SL rate applied each year, recalculated
        monthly for that year's portion.
        """
        self.ensure_one()
        self.schedule_ids.unlink()

        cost = float(self.acquisition_cost)
        salvage = float(self.salvage_value or 0)
        depreciable = max(0.0, cost - salvage)
        n = int(self.useful_life_months or 0)
        if n <= 0 or depreciable <= 0:
            return

        start = self.acquisition_date or fields.Date.context_today(self)
        entries = []
        if self.depreciation_method == "straight_line":
            monthly = round(depreciable / n, 2)
            accumulated = 0.0
            for i in range(n):
                d = start + relativedelta(months=i)
                amt = monthly if i < n - 1 else round(
                    depreciable - accumulated, 2,
                )
                accumulated += amt
                entries.append({
                    "asset_id": self.id,
                    "period_year": d.year,
                    "period_month": d.month,
                    "depreciation_amount": amt,
                    "accumulated_to_date": accumulated,
                    "book_value_after": cost - accumulated,
                })
        elif self.depreciation_method == "declining_balance":
            # 2× SL rate, applied to remaining book value each year.
            yearly_rate = (1.0 / (n / 12.0)) * 2.0
            book = cost
            accumulated = 0.0
            for i in range(n):
                d = start + relativedelta(months=i)
                # Cap at salvage
                yearly_dep = max(0.0, (book - salvage) * yearly_rate)
                monthly_dep = round(yearly_dep / 12.0, 2)
                if accumulated + monthly_dep > depreciable:
                    monthly_dep = round(depreciable - accumulated, 2)
                accumulated += monthly_dep
                book = cost - accumulated
                entries.append({
                    "asset_id": self.id,
                    "period_year": d.year,
                    "period_month": d.month,
                    "depreciation_amount": monthly_dep,
                    "accumulated_to_date": accumulated,
                    "book_value_after": book,
                })
        # units_of_production left for manual entry.

        if entries:
            self.env["kob.depreciation.entry"].create(entries)


class KobDepreciationEntry(models.Model):
    _name = "kob.depreciation.entry"
    _description = "Depreciation Entry"
    _order = "asset_id, period_year, period_month"
    _sql_constraints = [
        (
            "uniq_dep_period",
            "unique(asset_id, period_year, period_month)",
            "Duplicate depreciation period for this asset.",
        ),
    ]

    asset_id = fields.Many2one(
        "kob.fixed.asset", ondelete="cascade", required=True, index=True,
    )
    currency_id = fields.Many2one(
        related="asset_id.currency_id", store=True, readonly=True,
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    depreciation_amount = fields.Monetary(
        currency_field="currency_id", required=True,
    )
    accumulated_to_date = fields.Monetary(
        currency_field="currency_id", required=True,
    )
    book_value_after = fields.Monetary(
        currency_field="currency_id", required=True,
    )
    posted_at = fields.Datetime()
    move_id = fields.Many2one(
        "account.move", string="Journal Entry", ondelete="set null",
    )

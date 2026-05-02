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
        """Dispose asset — book gain/loss vs proceeds.

        gain  = proceeds - book_value  (Cr Other Income)
        loss  = book_value - proceeds  (Dr Other Expense)
        Always: Dr Cash/Bank (proceeds), Dr Accum.Dep (full), Cr Asset (cost).
        """
        for asset in self:
            if asset.state not in ("in_use", "fully_depreciated"):
                raise UserError(_(
                    "Only in-use or fully-depreciated assets can be disposed.",
                ))
            asset.write({
                "state": "disposed",
                "disposal_date": (
                    asset.disposal_date or fields.Date.context_today(asset)
                ),
            })
            asset._post_disposal_entry()

    def _post_disposal_entry(self):
        """Optional — only when GL accounts are wired and a default journal exists."""
        self.ensure_one()
        if not (
            self.asset_account_id
            and self.accumulated_depreciation_account_id
        ):
            return  # accounting wiring is optional
        journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if not journal:
            return
        proceeds = float(self.disposal_proceeds or 0)
        book_value = float(self.book_value or 0)
        cost = float(self.acquisition_cost or 0)
        accumulated = float(self.accumulated_depreciation or 0)
        gain = proceeds - book_value
        lines = [
            # Remove asset at cost
            (0, 0, {
                "account_id": self.asset_account_id.id,
                "name": _("Disposal — remove asset %s") % self.asset_code,
                "credit": cost,
                "debit": 0.0,
            }),
            # Reverse accumulated depreciation
            (0, 0, {
                "account_id": self.accumulated_depreciation_account_id.id,
                "name": _("Disposal — reverse accum. depr."),
                "debit": accumulated,
                "credit": 0.0,
            }),
        ]
        # Cash side — only if proceeds > 0 and we can find a bank/cash account
        if proceeds > 0:
            cash_acc = self.env["account.account"].search(
                [
                    ("account_type", "in", ("asset_cash", "asset_current")),
                    ("company_ids", "in", self.company_id.id),
                ],
                limit=1,
            )
            if cash_acc:
                lines.append((0, 0, {
                    "account_id": cash_acc.id,
                    "name": _("Disposal — proceeds"),
                    "debit": proceeds,
                    "credit": 0.0,
                }))
        # Gain / loss balancing line
        if abs(gain) > 0.005 and self.depreciation_expense_account_id:
            if gain > 0:
                lines.append((0, 0, {
                    "account_id": self.depreciation_expense_account_id.id,
                    "name": _("Gain on disposal"),
                    "credit": gain,
                    "debit": 0.0,
                }))
            else:
                lines.append((0, 0, {
                    "account_id": self.depreciation_expense_account_id.id,
                    "name": _("Loss on disposal"),
                    "debit": -gain,
                    "credit": 0.0,
                }))
        try:
            self.env["account.move"].create({
                "ref": _("Disposal of %s") % self.asset_code,
                "journal_id": journal.id,
                "date": self.disposal_date,
                "company_id": self.company_id.id,
                "line_ids": lines,
            })
        except Exception:
            # Fail-soft: keep state change even if posting fails (e.g. unbalanced)
            pass

    def action_cancel(self):
        for asset in self:
            if asset.state != "pending":
                raise UserError(_("Only pending assets can be cancelled."))
            asset.state = "cancelled"

    @api.model
    def cron_post_monthly_depreciation(self):
        """Post depreciation JEs for the previous month, idempotently.

        Looks at every active asset whose schedule has an unposted entry
        for the previous month. Creates the JE on a `general`-type
        journal in the asset's company. Skips if accounting accounts
        aren't wired.
        """
        today = fields.Date.context_today(self)
        target_year = today.year
        target_month = today.month - 1
        if target_month == 0:
            target_year -= 1
            target_month = 12

        entries = self.env["kob.depreciation.entry"].search([
            ("period_year", "=", target_year),
            ("period_month", "=", target_month),
            ("posted_at", "=", False),
            ("asset_id.state", "=", "in_use"),
        ])
        posted = 0
        for ent in entries:
            asset = ent.asset_id
            if not (
                asset.depreciation_expense_account_id
                and asset.accumulated_depreciation_account_id
            ):
                continue
            journal = self.env["account.journal"].search(
                [("type", "=", "general"),
                 ("company_id", "=", asset.company_id.id)],
                limit=1,
            )
            if not journal:
                continue
            try:
                move = self.env["account.move"].create({
                    "ref": _("Depreciation %s — %s/%s") % (
                        asset.asset_code, target_month, target_year,
                    ),
                    "journal_id": journal.id,
                    "date": fields.Date.from_string(
                        f"{target_year}-{target_month:02d}-01",
                    ),
                    "company_id": asset.company_id.id,
                    "line_ids": [
                        (0, 0, {
                            "account_id": asset.depreciation_expense_account_id.id,
                            "name": _("Depreciation expense"),
                            "debit": float(ent.depreciation_amount),
                            "credit": 0.0,
                        }),
                        (0, 0, {
                            "account_id": asset.accumulated_depreciation_account_id.id,
                            "name": _("Accumulated depreciation"),
                            "debit": 0.0,
                            "credit": float(ent.depreciation_amount),
                        }),
                    ],
                })
                ent.write({
                    "posted_at": fields.Datetime.now(),
                    "move_id": move.id,
                })
                posted += 1
            except Exception:
                continue
        # Recompute book value + auto-promote to fully_depreciated when all posted
        if posted:
            for asset in entries.mapped("asset_id"):
                asset._refresh_balances()
        return posted

    @api.model
    def cron_recompute_book_value(self):
        """Cheap nightly idempotent recompute on every active asset."""
        for asset in self.search([("state", "=", "in_use")]):
            asset._refresh_balances()

    def _refresh_balances(self):
        """accumulated = sum of posted depreciation entries; book = cost - acc."""
        for asset in self:
            posted = asset.schedule_ids.filtered(lambda e: e.posted_at)
            acc = sum(posted.mapped("depreciation_amount"))
            asset.accumulated_depreciation = acc
            asset.book_value = float(asset.acquisition_cost or 0) - acc
            # Auto-promote when fully depreciated
            if (
                asset.state == "in_use"
                and len(posted) >= len(asset.schedule_ids)
                and len(asset.schedule_ids) > 0
            ):
                asset.state = "fully_depreciated"

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

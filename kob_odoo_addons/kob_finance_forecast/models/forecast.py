from collections import defaultdict
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class KobFinanceForecast(models.Model):
    """One forecast row = one (account_id, year, period) combination
    with actuals YTD + projected end-of-year + variance vs budget."""

    _name = "kob.finance.forecast"
    _description = "KOB Predictive Financial Forecast"
    _order = "fiscal_year desc, account_id, period_index"

    company_id = fields.Many2one(
        "res.company",
        default=lambda s: s.env.company,
        required=True,
        index=True,
    )
    fiscal_year = fields.Integer(required=True, index=True)
    period_index = fields.Integer(
        required=True,
        help="Month 1-12 (or quarter 1-4 if granularity=quarter)",
    )
    granularity = fields.Selection(
        [("month", "Month"), ("quarter", "Quarter")],
        default="month",
        required=True,
    )
    account_id = fields.Many2one("account.account", required=True, index=True)
    account_type = fields.Selection(
        related="account_id.account_type",
        store=True,
    )

    actual_amount = fields.Monetary(
        help="Recorded posted journal entries for this account/period",
        currency_field="currency_id",
    )
    forecast_amount = fields.Monetary(
        help="Projected based on velocity + seasonality",
        currency_field="currency_id",
    )
    budget_amount = fields.Monetary(
        help="Budget target if a kob.procurement.budget or "
             "account.budget exists",
        currency_field="currency_id",
    )
    variance = fields.Monetary(
        compute="_compute_variance",
        store=True,
        currency_field="currency_id",
    )
    variance_pct = fields.Float(
        compute="_compute_variance",
        store=True,
    )
    confidence = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        compute="_compute_confidence",
        store=True,
    )
    is_projection = fields.Boolean(
        help="True if this period is in the future (forecast only, no actuals)",
    )
    refreshed_at = fields.Datetime(default=fields.Datetime.now)
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
    )

    _sql_constraints = [
        ("uniq_year_period_account_company",
         "unique(fiscal_year, period_index, granularity, account_id, company_id)",
         "Forecast already exists for this period+account+company"),
    ]

    @api.depends("actual_amount", "forecast_amount", "budget_amount")
    def _compute_variance(self):
        for r in self:
            actual_or_forecast = r.actual_amount if not r.is_projection else r.forecast_amount
            r.variance = actual_or_forecast - r.budget_amount
            if r.budget_amount:
                r.variance_pct = round(100.0 * r.variance / r.budget_amount, 2)
            else:
                r.variance_pct = 0.0

    @api.depends("is_projection", "actual_amount")
    def _compute_confidence(self):
        for r in self:
            if not r.is_projection:
                r.confidence = "high"
            else:
                # The further into the future, the lower the confidence
                today = fields.Date.context_today(r)
                period_start = date(r.fiscal_year, r.period_index, 1) \
                    if r.granularity == "month" \
                    else date(r.fiscal_year, ((r.period_index - 1) * 3) + 1, 1)
                months_ahead = (period_start - today).days / 30
                if months_ahead < 1:
                    r.confidence = "high"
                elif months_ahead < 3:
                    r.confidence = "medium"
                else:
                    r.confidence = "low"

    @api.model
    def refresh_for_year(self, year=None, granularity="month"):
        """Compute (or refresh) forecast rows for the given year for the
        active company. Wipes existing rows for that year first.

        Algorithm:
          1) Pull posted move lines for the year by account x month
          2) For past months → actual_amount only
          3) For future months → project from 3-month moving average
             and apply seasonality (same month last year × growth factor)
        """
        company = self.env.company
        year = year or fields.Date.context_today(self).year
        today = fields.Date.context_today(self)
        # Wipe rows for this year+company+granularity
        self.search([
            ("fiscal_year", "=", year),
            ("granularity", "=", granularity),
            ("company_id", "=", company.id),
        ]).unlink()

        # Aggregate posted entries (all P&L accounts) by account, month
        Line = self.env["account.move.line"]
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)
        lines = Line.search_read([
            ("move_id.state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("company_id", "=", company.id),
            ("account_id.account_type", "in", [
                "income", "income_other",
                "expense", "expense_depreciation", "expense_direct_cost",
            ]),
        ], ["account_id", "date", "balance"])

        actuals = defaultdict(lambda: defaultdict(float))  # actuals[acc][period_idx]
        for ln in lines:
            d = ln["date"]
            if isinstance(d, str):
                d = fields.Date.from_string(d)
            period = d.month if granularity == "month" else (d.month - 1) // 3 + 1
            actuals[ln["account_id"][0]][period] += ln["balance"]

        # Pull last-year same-period for seasonality
        last_year_lines = Line.search_read([
            ("move_id.state", "=", "posted"),
            ("date", ">=", date(year - 1, 1, 1)),
            ("date", "<=", date(year - 1, 12, 31)),
            ("company_id", "=", company.id),
        ], ["account_id", "date", "balance"])
        ly_actuals = defaultdict(lambda: defaultdict(float))
        for ln in last_year_lines:
            d = ln["date"]
            if isinstance(d, str):
                d = fields.Date.from_string(d)
            period = d.month if granularity == "month" else (d.month - 1) // 3 + 1
            ly_actuals[ln["account_id"][0]][period] += ln["balance"]

        # Build forecast rows
        last_period_with_actuals = today.month if granularity == "month" \
            else (today.month - 1) // 3 + 1
        max_period = 12 if granularity == "month" else 4

        rows = []
        for account_id in actuals.keys() | ly_actuals.keys():
            recent_periods = sorted(p for p, v in actuals[account_id].items()
                                    if p < last_period_with_actuals and v != 0)
            velocity = (
                sum(actuals[account_id][p] for p in recent_periods[-3:]) / max(1, len(recent_periods[-3:]))
                if recent_periods else 0
            )
            for period in range(1, max_period + 1):
                actual = actuals[account_id].get(period, 0.0)
                is_proj = period > last_period_with_actuals
                if is_proj:
                    # Seasonality factor: ratio of YTD this year vs last year
                    ytd_this = sum(actuals[account_id][p] for p in range(1, last_period_with_actuals + 1))
                    ytd_last = sum(ly_actuals[account_id][p] for p in range(1, last_period_with_actuals + 1))
                    growth = (ytd_this / ytd_last) if ytd_last else 1.0
                    seasonal_baseline = ly_actuals[account_id].get(period, velocity)
                    forecast = seasonal_baseline * growth
                else:
                    forecast = 0.0
                rows.append({
                    "company_id": company.id,
                    "fiscal_year": year,
                    "period_index": period,
                    "granularity": granularity,
                    "account_id": account_id,
                    "actual_amount": actual,
                    "forecast_amount": forecast,
                    "is_projection": is_proj,
                })
        if rows:
            self.create(rows)
        return len(rows)

    def action_refresh(self):
        n = self.refresh_for_year(self[0].fiscal_year if self else None,
                                  self[0].granularity if self else "month")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Forecast refreshed"),
                       "message": _("%s rows updated") % n,
                       "type": "success"},
        }

    @api.model
    def cron_refresh_current_year(self):
        """Daily cron: refresh forecast for current year (active company
        and any company with at least 1 posted move this year)."""
        year = fields.Date.context_today(self).year
        for co in self.env["res.company"].search([]):
            self.with_company(co).refresh_for_year(year)

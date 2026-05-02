# -*- coding: utf-8 -*-
"""KOB Account Report Engine.

Returns hierarchical row data for the AccountReport OWL component.
Each method returns a dict {columns: [...], rows: [{label, balance,
expandable, level, kind, lines: [...]}]}.
"""
from datetime import date
from collections import defaultdict

from odoo import api, models


class KobAccountReportEngine(models.AbstractModel):
    _name = "kob.account.report"
    _description = "KOB Account Report Engine"

    # ---------------------------------------------------------------- helpers

    @api.model
    def _period(self, year):
        if not year:
            year = date.today().year
        return date(year, 1, 1), date(year, 12, 31)

    @api.model
    def _domain(self, year, posted_only, journal_ids=None):
        d_from, d_to = self._period(year)
        domain = [("date", ">=", d_from), ("date", "<=", d_to)]
        if posted_only:
            domain.append(("parent_state", "=", "posted"))
        else:
            domain.append(("parent_state", "in", ("posted", "draft")))
        if journal_ids:
            domain.append(("journal_id", "in", journal_ids))
        if self.env.company:
            domain.append(("company_id", "=", self.env.company.id))
        return domain

    @api.model
    def _aml_groups(self, year, posted_only, fields=None, groupby=None):
        AML = self.env["account.move.line"]
        return AML._read_group(
            self._domain(year, posted_only),
            groupby=groupby or [],
            aggregates=fields or ["balance:sum"],
        )

    # ---------------------------------------------------------------- helpers
    @api.model
    def _round(self, v):
        return round(float(v or 0), 2)

    # ================================================================ P&L
    @api.model
    def get_profit_loss(self, year=None, posted_only=True):
        """Return P&L hierarchical rows.

        Buckets:
            Revenue                  → income
            Less Costs of Revenue    → expense_direct_cost
            Gross Profit             = Revenue - COGS
            Operating Expenses       → expense (further split by account name)
            Operating Income         = Gross Profit - OpEx
            Plus Other Income        → income_other
            Less Other Expenses      → expense_other (incl. depreciation)
            Net Profit               = Operating + Other
        """
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)

        groups = AML._read_group(
            domain,
            groupby=["account_id.account_type"],
            aggregates=["balance:sum"],
        )
        bal = {at: -float(b or 0) for at, b in groups}  # P&L sign-flip
        revenue = bal.get("income", 0) + bal.get("income_other", 0) - bal.get("income_other", 0)
        revenue = bal.get("income", 0)
        cogs = -bal.get("expense_direct_cost", 0)
        opex = -bal.get("expense", 0)
        depr = -bal.get("expense_depreciation", 0)
        other_income = bal.get("income_other", 0)
        other_expense = -bal.get("expense_other", 0)

        gross_profit = revenue - cogs
        operating_income = gross_profit - opex - depr
        net_profit = operating_income + other_income - other_expense

        rows = [
            {"label": "Revenue", "balance": self._round(revenue),
             "kind": "row", "expandable": True, "level": 0,
             "lines": self._lines_by_account(domain, "income")},

            {"label": "Less Costs of Revenue", "balance": self._round(cogs),
             "kind": "row", "expandable": True, "level": 0,
             "lines": self._lines_by_account(domain, "expense_direct_cost")},

            {"label": "Gross Profit", "balance": self._round(gross_profit),
             "kind": "subtotal", "level": 0},

            {"label": "Operating Expenses", "balance": self._round(opex + depr),
             "kind": "row", "expandable": True, "level": 0,
             "lines": (self._lines_by_account(domain, "expense")
                       + self._lines_by_account(domain, "expense_depreciation"))},

            {"label": "Operating Income (or Loss)",
             "balance": self._round(operating_income),
             "kind": "subtotal", "level": 0, "emphasis": True},

            {"label": "Plus Other Income", "balance": self._round(other_income),
             "kind": "row", "expandable": True, "level": 0,
             "lines": self._lines_by_account(domain, "income_other")},

            {"label": "Less Other Expenses", "balance": self._round(other_expense),
             "kind": "row", "expandable": True, "level": 0,
             "lines": self._lines_by_account(domain, "expense_other")},

            {"label": "Net Profit", "balance": self._round(net_profit),
             "kind": "subtotal", "level": 0, "emphasis": True, "final": True},
        ]
        return {
            "title": "Profit and Loss",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [{"label": "Balance", "align": "right"}],
            "rows": rows,
        }

    # ================================================================ Balance Sheet
    @api.model
    def get_balance_sheet(self, year=None, posted_only=True):
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)

        groups = AML._read_group(
            domain,
            groupby=["account_id.account_type"],
            aggregates=["balance:sum"],
        )
        bal = {at: float(b or 0) for at, b in groups}

        # Assets are debit-positive
        current_asset = bal.get("asset_current", 0)
        non_current_asset = (bal.get("asset_non_current", 0)
                             + bal.get("asset_fixed", 0))
        receivable = bal.get("asset_receivable", 0)
        cash = bal.get("asset_cash", 0)
        prepay = bal.get("asset_prepayments", 0)
        total_assets = (current_asset + non_current_asset + receivable
                        + cash + prepay)

        # Liabilities are credit-positive (sign flip)
        current_liab = -bal.get("liability_current", 0)
        non_current_liab = -bal.get("liability_non_current", 0)
        payable = -bal.get("liability_payable", 0)
        credit_card = -bal.get("liability_credit_card", 0)
        total_liab = current_liab + non_current_liab + payable + credit_card

        equity = -bal.get("equity", 0)
        unalloc = -bal.get("equity_unaffected", 0)
        total_equity = equity + unalloc

        rows = [
            {"label": "Assets", "kind": "section", "level": 0},
            {"label": "Current Assets", "balance": self._round(current_asset),
             "kind": "row", "expandable": True, "level": 1,
             "lines": self._lines_by_account(domain, "asset_current")},
            {"label": "Bank and Cash", "balance": self._round(cash),
             "kind": "row", "expandable": True, "level": 1,
             "lines": self._lines_by_account(domain, "asset_cash")},
            {"label": "Receivables", "balance": self._round(receivable),
             "kind": "row", "expandable": True, "level": 1,
             "lines": self._lines_by_account(domain, "asset_receivable")},
            {"label": "Prepayments", "balance": self._round(prepay),
             "kind": "row", "expandable": True, "level": 1,
             "lines": self._lines_by_account(domain, "asset_prepayments")},
            {"label": "Non-current Assets",
             "balance": self._round(non_current_asset),
             "kind": "row", "expandable": True, "level": 1,
             "lines": (self._lines_by_account(domain, "asset_non_current")
                       + self._lines_by_account(domain, "asset_fixed"))},
            {"label": "Total Assets", "balance": self._round(total_assets),
             "kind": "subtotal", "level": 0, "emphasis": True},

            {"label": "Liabilities", "kind": "section", "level": 0},
            {"label": "Current Liabilities", "balance": self._round(current_liab),
             "kind": "row", "expandable": True, "level": 1,
             "lines": self._lines_by_account(domain, "liability_current")},
            {"label": "Payables", "balance": self._round(payable),
             "kind": "row", "expandable": True, "level": 1,
             "lines": self._lines_by_account(domain, "liability_payable")},
            {"label": "Non-current Liabilities",
             "balance": self._round(non_current_liab),
             "kind": "row", "expandable": True, "level": 1,
             "lines": self._lines_by_account(domain, "liability_non_current")},
            {"label": "Total Liabilities", "balance": self._round(total_liab),
             "kind": "subtotal", "level": 0, "emphasis": True},

            {"label": "Equity", "kind": "section", "level": 0},
            {"label": "Equity", "balance": self._round(equity),
             "kind": "row", "expandable": True, "level": 1,
             "lines": self._lines_by_account(domain, "equity")},
            {"label": "Current Year Earnings", "balance": self._round(unalloc),
             "kind": "row", "expandable": True, "level": 1,
             "lines": self._lines_by_account(domain, "equity_unaffected")},
            {"label": "Total Equity", "balance": self._round(total_equity),
             "kind": "subtotal", "level": 0, "emphasis": True},

            {"label": "Liabilities + Equity",
             "balance": self._round(total_liab + total_equity),
             "kind": "subtotal", "level": 0, "emphasis": True, "final": True},
        ]
        return {
            "title": "Balance Sheet",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [{"label": "Balance", "align": "right"}],
            "rows": rows,
        }

    # ================================================================ Journal Audit
    @api.model
    def get_journal_audit(self, year=None, posted_only=True):
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)
        groups = AML._read_group(
            domain,
            groupby=["journal_id"],
            aggregates=["debit:sum", "credit:sum"],
        )
        rows = []
        for journal, debit, credit in groups:
            rows.append({
                "label": journal.name,
                "code": journal.code,
                "debit": self._round(debit or 0),
                "credit": self._round(credit or 0),
                "balance": self._round((debit or 0) - (credit or 0)),
                "kind": "row", "expandable": True, "level": 0,
                "lines": [],
            })
        return {
            "title": "Journal Audit",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Code", "align": "left", "key": "code"},
                {"label": "Debit", "align": "right", "key": "debit"},
                {"label": "Credit", "align": "right", "key": "credit"},
                {"label": "Balance", "align": "right", "key": "balance"},
            ],
            "rows": rows,
            "tax_summary": self._tax_summary(domain),
        }

    # ================================================================ Trial Balance
    @api.model
    def get_trial_balance(self, year=None, posted_only=True):
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)
        groups = AML._read_group(
            domain,
            groupby=["account_id"],
            aggregates=["debit:sum", "credit:sum", "balance:sum"],
        )
        rows = []
        for account, debit, credit, balance in groups:
            if not account:
                continue
            rows.append({
                "label": f"{account.code} {account.name}",
                "code": account.code,
                "debit": self._round(debit or 0),
                "credit": self._round(credit or 0),
                "balance": self._round(balance or 0),
                "kind": "row", "level": 0,
            })
        rows.sort(key=lambda r: r["code"])
        # Totals
        td = sum(r["debit"] for r in rows)
        tc = sum(r["credit"] for r in rows)
        rows.append({
            "label": "Total", "code": "",
            "debit": self._round(td), "credit": self._round(tc),
            "balance": self._round(td - tc),
            "kind": "subtotal", "level": 0, "emphasis": True, "final": True,
        })
        return {
            "title": "Trial Balance",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Code", "align": "left", "key": "code"},
                {"label": "Debit", "align": "right", "key": "debit"},
                {"label": "Credit", "align": "right", "key": "credit"},
                {"label": "Balance", "align": "right", "key": "balance"},
            ],
            "rows": rows,
        }

    # ================================================================ helpers
    @api.model
    def _lines_by_account(self, base_domain, account_type):
        AML = self.env["account.move.line"]
        domain = list(base_domain) + [("account_id.account_type", "=", account_type)]
        groups = AML._read_group(
            domain,
            groupby=["account_id"],
            aggregates=["balance:sum"],
        )
        out = []
        for account, balance in groups:
            if not account:
                continue
            sign = -1 if account_type.startswith(("income", "liability", "equity")) else 1
            out.append({
                "label": f"{account.code} {account.name}",
                "balance": self._round(sign * (balance or 0)),
                "kind": "leaf", "level": 1,
            })
        out.sort(key=lambda r: r["label"])
        return out

    @api.model
    def _tax_summary(self, base_domain):
        AML = self.env["account.move.line"]

        # Tax amounts: sum balance per tax_line_id
        tax_lines = AML._read_group(
            list(base_domain) + [("tax_line_id", "!=", False)],
            groupby=["tax_line_id"],
            aggregates=["balance:sum", "tax_base_amount:sum"],
        )
        applied = []
        for tax, bal, base in tax_lines:
            tax_amount = abs(float(bal or 0))
            applied.append({
                "name": tax.name,
                "base_amount": self._round(abs(float(base or 0))),
                "tax_amount": self._round(tax_amount),
                "deductible": self._round(tax_amount if tax.type_tax_use == "purchase" else 0),
                "due": self._round(tax_amount if tax.type_tax_use == "sale" else 0),
            })
        return {"applied": applied}

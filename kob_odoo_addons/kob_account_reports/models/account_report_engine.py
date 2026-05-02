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

    # ================================================================ Cash Flow
    @api.model
    def get_cash_flow(self, year=None, posted_only=True):
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)
        groups = AML._read_group(
            domain, groupby=["account_id.account_type"], aggregates=["balance:sum"],
        )
        bal = {at: float(b or 0) for at, b in groups}

        net_income = -(bal.get("income", 0) + bal.get("income_other", 0)
                       + bal.get("expense", 0) + bal.get("expense_direct_cost", 0)
                       + bal.get("expense_depreciation", 0)
                       + bal.get("expense_other", 0))
        depreciation = -bal.get("expense_depreciation", 0)
        ar_change = bal.get("asset_receivable", 0)
        ap_change = -bal.get("liability_payable", 0)
        operating = net_income + depreciation - ar_change + ap_change

        capex = bal.get("asset_fixed", 0) + bal.get("asset_non_current", 0)
        investing = -capex

        debt_change = -bal.get("liability_non_current", 0)
        equity_change = -bal.get("equity", 0)
        financing = debt_change + equity_change

        net_cash = operating + investing + financing
        cash = bal.get("asset_cash", 0)

        rows = [
            {"label": "Cash flows from Operating Activities",
             "kind": "section", "level": 0},
            {"label": "Net Profit", "balance": self._round(net_income),
             "kind": "row", "level": 1},
            {"label": "Add back: Depreciation",
             "balance": self._round(depreciation),
             "kind": "row", "level": 1},
            {"label": "Changes in Receivables",
             "balance": self._round(-ar_change),
             "kind": "row", "level": 1},
            {"label": "Changes in Payables",
             "balance": self._round(ap_change),
             "kind": "row", "level": 1},
            {"label": "Net cash from operations",
             "balance": self._round(operating),
             "kind": "subtotal", "level": 0, "emphasis": True},

            {"label": "Cash flows from Investing Activities",
             "kind": "section", "level": 0},
            {"label": "Capex / Asset Movements",
             "balance": self._round(investing),
             "kind": "row", "level": 1},
            {"label": "Net cash from investing",
             "balance": self._round(investing),
             "kind": "subtotal", "level": 0, "emphasis": True},

            {"label": "Cash flows from Financing Activities",
             "kind": "section", "level": 0},
            {"label": "Long-term Debt Changes",
             "balance": self._round(debt_change),
             "kind": "row", "level": 1},
            {"label": "Equity Changes",
             "balance": self._round(equity_change),
             "kind": "row", "level": 1},
            {"label": "Net cash from financing",
             "balance": self._round(financing),
             "kind": "subtotal", "level": 0, "emphasis": True},

            {"label": "Net Increase in Cash",
             "balance": self._round(net_cash),
             "kind": "subtotal", "level": 0, "emphasis": True, "final": True},
            {"label": "Closing Cash Position",
             "balance": self._round(cash),
             "kind": "row", "level": 0},
        ]
        return {
            "title": "Cash Flow Statement",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [{"label": "Balance", "align": "right"}],
            "rows": rows,
        }

    # ================================================================ Executive Summary
    @api.model
    def get_executive_summary(self, year=None, posted_only=True):
        pl = self.get_profit_loss(year, posted_only)
        bs = self.get_balance_sheet(year, posted_only)

        revenue = next((r["balance"] for r in pl["rows"] if r["label"] == "Revenue"), 0)
        gross = next((r["balance"] for r in pl["rows"] if r["label"] == "Gross Profit"), 0)
        op_inc = next((r["balance"] for r in pl["rows"]
                       if r["label"].startswith("Operating Income")), 0)
        net_profit = next((r["balance"] for r in pl["rows"] if r["label"] == "Net Profit"), 0)
        total_assets = next((r["balance"] for r in bs["rows"] if r["label"] == "Total Assets"), 0)
        total_liab = next((r["balance"] for r in bs["rows"] if r["label"] == "Total Liabilities"), 0)
        cash = next((r["balance"] for r in bs["rows"] if r["label"] == "Bank and Cash"), 0)
        ar = next((r["balance"] for r in bs["rows"] if r["label"] == "Receivables"), 0)
        ap = next((r["balance"] for r in bs["rows"] if r["label"] == "Payables"), 0)

        gross_margin = (gross / revenue * 100) if revenue else 0
        op_margin = (op_inc / revenue * 100) if revenue else 0
        net_margin = (net_profit / revenue * 100) if revenue else 0

        rows = [
            {"label": "Profitability", "kind": "section", "level": 0},
            {"label": "Revenue", "balance": revenue, "kind": "row", "level": 1},
            {"label": "Gross Profit", "balance": gross, "kind": "row", "level": 1},
            {"label": "Operating Income", "balance": op_inc, "kind": "row", "level": 1},
            {"label": "Net Profit", "balance": net_profit,
             "kind": "subtotal", "level": 0, "emphasis": True},
            {"label": "Margins (%)", "kind": "section", "level": 0},
            {"label": "Gross Margin", "balance": self._round(gross_margin),
             "kind": "row", "level": 1},
            {"label": "Operating Margin", "balance": self._round(op_margin),
             "kind": "row", "level": 1},
            {"label": "Net Margin", "balance": self._round(net_margin),
             "kind": "row", "level": 1},
            {"label": "Position", "kind": "section", "level": 0},
            {"label": "Total Assets", "balance": total_assets, "kind": "row", "level": 1},
            {"label": "Total Liabilities", "balance": total_liab, "kind": "row", "level": 1},
            {"label": "Cash on Hand", "balance": cash, "kind": "row", "level": 1},
            {"label": "Receivables", "balance": ar, "kind": "row", "level": 1},
            {"label": "Payables", "balance": ap, "kind": "row", "level": 1},
        ]
        return {
            "title": "Executive Summary",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [{"label": "Value", "align": "right"}],
            "rows": rows,
        }

    # ================================================================ Tax Return
    @api.model
    def get_tax_return(self, year=None, posted_only=True):
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)
        tax_lines = AML._read_group(
            list(domain) + [("tax_line_id", "!=", False)],
            groupby=["tax_line_id"],
            aggregates=["balance:sum", "tax_base_amount:sum"],
        )
        sale_rows, purchase_rows = [], []
        for tax, bal, base in tax_lines:
            row = {
                "label": tax.name,
                "code": tax.description or tax.name,
                "base": self._round(abs(float(base or 0))),
                "tax": self._round(abs(float(bal or 0))),
                "balance": self._round(abs(float(bal or 0))),
                "kind": "row", "level": 1,
            }
            if tax.type_tax_use == "sale":
                sale_rows.append(row)
            elif tax.type_tax_use == "purchase":
                purchase_rows.append(row)

        sale_total = sum(r["tax"] for r in sale_rows)
        purchase_total = sum(r["tax"] for r in purchase_rows)
        net = sale_total - purchase_total

        rows = [{"label": "Output VAT (Sales)", "kind": "section", "level": 0}]
        rows.extend(sale_rows)
        rows.append({"label": "Total Output VAT", "balance": self._round(sale_total),
                     "kind": "subtotal", "level": 0, "emphasis": True})
        rows.append({"label": "Input VAT (Purchases)", "kind": "section", "level": 0})
        rows.extend(purchase_rows)
        rows.append({"label": "Total Input VAT", "balance": self._round(purchase_total),
                     "kind": "subtotal", "level": 0, "emphasis": True})
        rows.append({"label": "Net VAT (payable / refundable)",
                     "balance": self._round(net),
                     "kind": "subtotal", "level": 0, "emphasis": True, "final": True})
        return {
            "title": "Tax Return",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Code", "align": "left", "key": "code"},
                {"label": "Base", "align": "right", "key": "base"},
                {"label": "Tax", "align": "right", "key": "tax"},
            ],
            "rows": rows,
        }

    # ================================================================ General Ledger
    @api.model
    def get_general_ledger(self, year=None, posted_only=True):
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)
        groups = AML._read_group(
            domain, groupby=["account_id"],
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
                "kind": "row", "expandable": False, "level": 0,
            })
        rows.sort(key=lambda r: r["code"])
        td = sum(r["debit"] for r in rows)
        tc = sum(r["credit"] for r in rows)
        rows.append({
            "label": "Total", "code": "",
            "debit": self._round(td), "credit": self._round(tc),
            "balance": self._round(td - tc),
            "kind": "subtotal", "level": 0, "emphasis": True, "final": True,
        })
        return {
            "title": "General Ledger",
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

    # ================================================================ Partner Ledger
    @api.model
    def get_partner_ledger(self, year=None, posted_only=True, account_type=None):
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)
        if account_type:
            domain = list(domain) + [("account_id.account_type", "=", account_type)]
        else:
            domain = list(domain) + [
                ("account_id.account_type", "in", ("asset_receivable", "liability_payable"))
            ]
        groups = AML._read_group(
            domain, groupby=["partner_id"],
            aggregates=["debit:sum", "credit:sum", "balance:sum"],
        )
        rows = []
        for partner, debit, credit, balance in groups:
            rows.append({
                "label": (partner.name if partner else "(no partner)"),
                "code": str(partner.id) if partner else "",
                "debit": self._round(debit or 0),
                "credit": self._round(credit or 0),
                "balance": self._round(balance or 0),
                "kind": "row", "level": 0,
            })
        rows.sort(key=lambda r: r["label"])
        td = sum(r["debit"] for r in rows)
        tc = sum(r["credit"] for r in rows)
        rows.append({
            "label": "Total", "code": "",
            "debit": self._round(td), "credit": self._round(tc),
            "balance": self._round(td - tc),
            "kind": "subtotal", "level": 0, "emphasis": True, "final": True,
        })
        return {
            "title": "Partner Ledger",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Partner", "align": "left", "key": "code"},
                {"label": "Debit", "align": "right", "key": "debit"},
                {"label": "Credit", "align": "right", "key": "credit"},
                {"label": "Balance", "align": "right", "key": "balance"},
            ],
            "rows": rows,
        }

    # ================================================================ Aged Receivable / Payable
    @api.model
    def _aged(self, account_type, posted_only):
        AML = self.env["account.move.line"]
        today = date.today()
        domain = [("account_id.account_type", "=", account_type),
                  ("amount_residual", "!=", 0),
                  ("parent_state", "=", "posted")]
        if not posted_only:
            domain = [("account_id.account_type", "=", account_type),
                      ("amount_residual", "!=", 0)]

        lines = AML.search(domain)
        partners = {}
        for ln in lines:
            d = ln.date_maturity or ln.date or today
            age_days = (today - d).days
            if age_days <= 0:
                bucket = "current"
            elif age_days <= 30:
                bucket = "b30"
            elif age_days <= 60:
                bucket = "b60"
            elif age_days <= 90:
                bucket = "b90"
            elif age_days <= 120:
                bucket = "b120"
            else:
                bucket = "older"
            p = ln.partner_id
            key = p.id if p else 0
            entry = partners.setdefault(key, {
                "label": p.name if p else "(no partner)",
                "current": 0, "b30": 0, "b60": 0, "b90": 0, "b120": 0, "older": 0,
                "total": 0,
            })
            v = float(ln.amount_residual or 0)
            entry[bucket] += v
            entry["total"] += v

        rows = []
        for key, e in partners.items():
            rows.append({
                "label": e["label"],
                "current": self._round(e["current"]),
                "b30": self._round(e["b30"]),
                "b60": self._round(e["b60"]),
                "b90": self._round(e["b90"]),
                "b120": self._round(e["b120"]),
                "older": self._round(e["older"]),
                "total": self._round(e["total"]),
                "balance": self._round(e["total"]),
                "kind": "row", "level": 0,
            })
        rows.sort(key=lambda r: -abs(r["total"]))
        # Totals
        totals = {k: sum(r[k] for r in rows)
                  for k in ("current", "b30", "b60", "b90", "b120", "older", "total")}
        rows.append({
            "label": "Total",
            **{k: self._round(totals[k]) for k in totals},
            "balance": self._round(totals["total"]),
            "kind": "subtotal", "level": 0, "emphasis": True, "final": True,
        })
        return rows

    @api.model
    def get_aged_receivable(self, year=None, posted_only=True):
        rows = self._aged("asset_receivable", posted_only)
        return {
            "title": "Aged Receivable",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Current", "align": "right", "key": "current"},
                {"label": "1-30", "align": "right", "key": "b30"},
                {"label": "31-60", "align": "right", "key": "b60"},
                {"label": "61-90", "align": "right", "key": "b90"},
                {"label": "91-120", "align": "right", "key": "b120"},
                {"label": "Older", "align": "right", "key": "older"},
                {"label": "Total", "align": "right", "key": "total"},
            ],
            "rows": rows,
        }

    @api.model
    def get_aged_payable(self, year=None, posted_only=True):
        rows = self._aged("liability_payable", posted_only)
        return {
            "title": "Aged Payable",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Current", "align": "right", "key": "current"},
                {"label": "1-30", "align": "right", "key": "b30"},
                {"label": "31-60", "align": "right", "key": "b60"},
                {"label": "61-90", "align": "right", "key": "b90"},
                {"label": "91-120", "align": "right", "key": "b120"},
                {"label": "Older", "align": "right", "key": "older"},
                {"label": "Total", "align": "right", "key": "total"},
            ],
            "rows": rows,
        }

    # ================================================================ Invoice Analysis
    @api.model
    def get_invoice_analysis(self, year=None, posted_only=True):
        Move = self.env["account.move"]
        d_from, d_to = self._period(year)
        domain = [("invoice_date", ">=", d_from), ("invoice_date", "<=", d_to),
                  ("move_type", "in",
                   ["out_invoice", "out_refund", "in_invoice", "in_refund"])]
        if posted_only:
            domain.append(("state", "=", "posted"))

        groups = Move._read_group(
            domain, groupby=["move_type"],
            aggregates=["amount_total:sum", "id:count"],
        )
        type_label = {
            "out_invoice": "Customer Invoices",
            "out_refund": "Customer Credit Notes",
            "in_invoice": "Vendor Bills",
            "in_refund": "Vendor Refunds",
        }
        rows = []
        total_count = 0
        total_amount = 0
        for mt, amount, n in groups:
            rows.append({
                "label": type_label.get(mt, mt),
                "code": mt,
                "count": n,
                "balance": self._round(amount or 0),
                "kind": "row", "level": 0,
            })
            total_count += n
            total_amount += float(amount or 0)
        rows.append({
            "label": "Total", "code": "",
            "count": total_count,
            "balance": self._round(total_amount),
            "kind": "subtotal", "level": 0, "emphasis": True, "final": True,
        })
        return {
            "title": "Invoice Analysis",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Type", "align": "left", "key": "code"},
                {"label": "Count", "align": "right", "key": "count"},
                {"label": "Total", "align": "right", "key": "balance"},
            ],
            "rows": rows,
        }

    # ================================================================ Analytic Report
    @api.model
    def get_analytic_report(self, year=None, posted_only=True):
        AAL = self.env.get("account.analytic.line")
        if AAL is None:
            return self._empty_report("Analytic Report",
                                      "account.analytic.line model not available")
        d_from, d_to = self._period(year)
        domain = [("date", ">=", d_from), ("date", "<=", d_to)]
        groups = AAL._read_group(
            domain, groupby=["account_id"],
            aggregates=["amount:sum"],
        )
        rows = []
        for account, amount in groups:
            if not account:
                continue
            rows.append({
                "label": account.name,
                "code": (account.code if hasattr(account, "code") else ""),
                "balance": self._round(amount or 0),
                "kind": "row", "level": 0,
            })
        rows.sort(key=lambda r: -r["balance"])
        total = sum(r["balance"] for r in rows)
        rows.append({
            "label": "Total", "code": "",
            "balance": self._round(total),
            "kind": "subtotal", "level": 0, "emphasis": True, "final": True,
        })
        return {
            "title": "Analytic Report",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Code", "align": "left", "key": "code"},
                {"label": "Amount", "align": "right", "key": "balance"},
            ],
            "rows": rows,
        }

    # ================================================================ Unrealized Currency Gains/Losses
    @api.model
    def get_unrealized_fx(self, year=None, posted_only=True):
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)
        domain = list(domain) + [
            ("currency_id", "!=", False),
            ("currency_id", "!=", self.env.company.currency_id.id),
            ("amount_residual_currency", "!=", 0),
        ]
        groups = AML._read_group(
            domain, groupby=["currency_id"],
            aggregates=["amount_residual_currency:sum", "amount_residual:sum"],
        )
        rows = []
        for currency, fx_amt, base_amt in groups:
            rows.append({
                "label": currency.name if currency else "(none)",
                "code": currency.name if currency else "",
                "balance": self._round(fx_amt or 0),
                "base": self._round(base_amt or 0),
                "kind": "row", "level": 0,
            })
        return {
            "title": "Unrealized Currency Gains/Losses",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Currency", "align": "left", "key": "code"},
                {"label": "FX Amount", "align": "right", "key": "balance"},
                {"label": "Base", "align": "right", "key": "base"},
            ],
            "rows": rows,
        }

    # ================================================================ Deferred Expense / Revenue
    @api.model
    def _deferred(self, account_type):
        AML = self.env["account.move.line"]
        today = date.today()
        domain = [("account_id.account_type", "=", account_type),
                  ("date", ">", today)]
        groups = AML._read_group(
            domain, groupby=["account_id"],
            aggregates=["balance:sum"],
        )
        rows = []
        for account, balance in groups:
            if not account:
                continue
            rows.append({
                "label": f"{account.code} {account.name}",
                "code": account.code,
                "balance": self._round(balance or 0),
                "kind": "row", "level": 0,
            })
        return rows

    @api.model
    def get_deferred_expense(self, year=None, posted_only=True):
        rows = self._deferred("asset_prepayments")
        return {
            "title": "Deferred Expense",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Code", "align": "left", "key": "code"},
                {"label": "Balance", "align": "right", "key": "balance"},
            ],
            "rows": rows,
        }

    @api.model
    def get_deferred_revenue(self, year=None, posted_only=True):
        rows = self._deferred("liability_current")
        return {
            "title": "Deferred Revenue",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Code", "align": "left", "key": "code"},
                {"label": "Balance", "align": "right", "key": "balance"},
            ],
            "rows": rows,
        }

    # ================================================================ Depreciation Schedule
    @api.model
    def get_depreciation_schedule(self, year=None, posted_only=True):
        Asset = self.env.get("kob.fixed.asset") or self.env.get("account.asset")
        if Asset is None:
            return self._empty_report("Depreciation Schedule",
                                      "Asset model not installed")
        records = Asset.search([])
        rows = []
        for a in records:
            label = getattr(a, "name", str(a.id))
            cost = float(getattr(a, "purchase_value", None)
                         or getattr(a, "original_value", None)
                         or getattr(a, "value", 0) or 0)
            book = float(getattr(a, "book_value", None)
                         or getattr(a, "value_residual", 0) or 0)
            rows.append({
                "label": label,
                "code": getattr(a, "code", "") or "",
                "cost": self._round(cost),
                "book": self._round(book),
                "balance": self._round(book),
                "kind": "row", "level": 0,
            })
        total_cost = sum(r["cost"] for r in rows)
        total_book = sum(r["book"] for r in rows)
        rows.append({
            "label": "Total", "code": "",
            "cost": self._round(total_cost),
            "book": self._round(total_book),
            "balance": self._round(total_book),
            "kind": "subtotal", "level": 0, "emphasis": True, "final": True,
        })
        return {
            "title": "Depreciation Schedule",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Code", "align": "left", "key": "code"},
                {"label": "Cost", "align": "right", "key": "cost"},
                {"label": "Book Value", "align": "right", "key": "book"},
            ],
            "rows": rows,
        }

    # ================================================================ Disallowed Expenses
    @api.model
    def get_disallowed_expenses(self, year=None, posted_only=True):
        AML = self.env["account.move.line"]
        domain = self._domain(year, posted_only)
        # Best-effort: accounts whose name/code mentions "non-deductible" or marked
        domain = list(domain) + [
            "|",
            ("account_id.name", "ilike", "non-deductible"),
            ("account_id.name", "ilike", "disallowed"),
        ]
        groups = AML._read_group(
            domain, groupby=["account_id"], aggregates=["balance:sum"],
        )
        rows = []
        for account, balance in groups:
            if not account:
                continue
            rows.append({
                "label": f"{account.code} {account.name}",
                "code": account.code,
                "balance": self._round(balance or 0),
                "kind": "row", "level": 0,
            })
        if not rows:
            return self._empty_report("Disallowed Expenses",
                                      "No accounts flagged as disallowed/non-deductible.")
        total = sum(r["balance"] for r in rows)
        rows.append({
            "label": "Total", "code": "",
            "balance": self._round(total),
            "kind": "subtotal", "level": 0, "emphasis": True, "final": True,
        })
        return {
            "title": "Disallowed Expenses",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Code", "align": "left", "key": "code"},
                {"label": "Balance", "align": "right", "key": "balance"},
            ],
            "rows": rows,
        }

    # ================================================================ Budget Report
    @api.model
    def get_budget_report(self, year=None, posted_only=True):
        Budget = self.env.get("budget.budget")
        if Budget is None:
            return self._empty_report("Budget Report",
                                      "Budget module not installed")
        rows = []
        for b in Budget.search([]):
            rows.append({
                "label": b.display_name,
                "code": getattr(b, "code", ""),
                "balance": self._round(getattr(b, "amount", 0)),
                "kind": "row", "level": 0,
            })
        if not rows:
            return self._empty_report("Budget Report", "No budgets defined.")
        total = sum(r["balance"] for r in rows)
        rows.append({"label": "Total", "balance": self._round(total),
                     "kind": "subtotal", "level": 0,
                     "emphasis": True, "final": True})
        return {
            "title": "Budget Report",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [{"label": "Amount", "align": "right", "key": "balance"}],
            "rows": rows,
        }

    # ================================================================ Loans Analysis
    @api.model
    def get_loans_analysis(self, year=None, posted_only=True):
        Loan = self.env.get("kob.intercompany.loan") or self.env.get("account.loan")
        if Loan is None:
            return self._empty_report("Loans Analysis",
                                      "Loan model not available")
        loans = Loan.search([])
        rows = []
        for L in loans:
            principal = float(getattr(L, "amount", None)
                              or getattr(L, "principal", 0) or 0)
            rate = float(getattr(L, "interest_rate", None)
                         or getattr(L, "rate", 0) or 0)
            balance = float(getattr(L, "outstanding_balance", None)
                            or getattr(L, "balance", principal) or 0)
            rows.append({
                "label": getattr(L, "name", str(L.id)),
                "code": getattr(L, "code", "") or "",
                "principal": self._round(principal),
                "rate": rate,
                "balance": self._round(balance),
                "kind": "row", "level": 0,
            })
        if not rows:
            return self._empty_report("Loans Analysis", "No loans recorded.")
        total = sum(r["balance"] for r in rows)
        rows.append({"label": "Total", "balance": self._round(total),
                     "kind": "subtotal", "level": 0,
                     "emphasis": True, "final": True})
        return {
            "title": "Loans Analysis",
            "year": year or date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [
                {"label": "Code", "align": "left", "key": "code"},
                {"label": "Principal", "align": "right", "key": "principal"},
                {"label": "Rate %", "align": "right", "key": "rate"},
                {"label": "Outstanding", "align": "right", "key": "balance"},
            ],
            "rows": rows,
        }

    # ================================================================ Helper: empty report
    @api.model
    def _empty_report(self, title, message):
        return {
            "title": title,
            "year": date.today().year,
            "currency": self.env.company.currency_id.symbol,
            "columns": [{"label": "Status", "align": "left"}],
            "rows": [{"label": message, "kind": "row", "level": 0}],
        }

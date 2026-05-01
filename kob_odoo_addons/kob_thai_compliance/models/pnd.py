# -*- coding: utf-8 -*-
"""PND withholding tax filing + lines."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .services import compute_monthly_wht


class KobPndFiling(models.Model):
    _name = "kob.pnd.filing"
    _description = "PND Withholding Tax Filing"
    _order = "period_year desc, period_month desc"
    _sql_constraints = [
        (
            "uniq_period",
            "unique(company_id, filing_type, period_year, period_month)",
            "Filing already exists for this period and type.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    filing_type = fields.Selection(
        [
            ("pnd1", "PND1 — Salaried employees"),
            ("pnd1a", "PND1A — Annual"),
            ("pnd2", "PND2 — Investment income"),
            ("pnd3", "PND3 — Service WHT"),
            ("pnd53", "PND53 — Corporate WHT"),
        ],
        default="pnd1",
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("calculated", "Calculated"),
            ("submitted", "Submitted"),
            ("amended", "Amended"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    line_ids = fields.One2many("kob.pnd.filing.line", "filing_id", string="Lines")
    total_gross_wage = fields.Monetary(currency_field="currency_id", readonly=True)
    total_wht = fields.Monetary(currency_field="currency_id", readonly=True)
    submitted_at = fields.Datetime()
    submitted_by = fields.Many2one("res.users")
    rd_receipt_number = fields.Char(string="RD Receipt No.")
    note = fields.Text()
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )

    def action_calculate(self):
        for filing in self:
            if filing.state not in ("draft", "calculated"):
                raise UserError(
                    _("Cannot calculate filing in state %s.") % filing.state
                )
            filing.line_ids.unlink()

            contrib = self.env["kob.sso.contribution"].search(
                [
                    ("company_id", "=", filing.company_id.id),
                    ("period_year", "=", filing.period_year),
                    ("period_month", "=", filing.period_month),
                ]
            )
            total_gross = 0.0
            total_wht = 0.0
            line_vals = []
            for c in contrib:
                gross = float(c.gross_wage or 0)
                deductions = float(c.employee_amount or 0)
                taxable = max(0.0, gross - deductions)
                wht, rate = compute_monthly_wht(taxable)
                line_vals.append({
                    "filing_id": filing.id,
                    "employee_id": c.employee_id.id,
                    "employee_name": c.employee_id.name,
                    "national_id": c.employee_id.identification_id or False,
                    "gross_wage": gross,
                    "deductions": deductions,
                    "taxable_income": taxable,
                    "wht_amount": wht,
                    "wht_rate_pct": rate,
                })
                total_gross += gross
                total_wht += wht
            self.env["kob.pnd.filing.line"].create(line_vals)
            filing.total_gross_wage = round(total_gross, 2)
            filing.total_wht = round(total_wht, 2)
            filing.state = "calculated"

    def action_submit(self):
        for filing in self:
            if filing.state != "calculated":
                raise UserError(_("Only calculated filings can be submitted."))
            filing.write({
                "state": "submitted",
                "submitted_at": fields.Datetime.now(),
                "submitted_by": self.env.user.id,
            })


class KobPndFilingLine(models.Model):
    _name = "kob.pnd.filing.line"
    _description = "PND Filing Line"

    filing_id = fields.Many2one("kob.pnd.filing", ondelete="cascade", required=True)
    employee_id = fields.Many2one("hr.employee")
    employee_name = fields.Char()
    national_id = fields.Char()
    gross_wage = fields.Monetary(currency_field="currency_id")
    deductions = fields.Monetary(currency_field="currency_id")
    taxable_income = fields.Monetary(currency_field="currency_id")
    wht_amount = fields.Monetary(currency_field="currency_id")
    wht_rate_pct = fields.Float()
    currency_id = fields.Many2one(
        related="filing_id.currency_id", store=True, readonly=True,
    )

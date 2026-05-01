# -*- coding: utf-8 -*-
"""Intercompany loan — A→B with installment schedule + outstanding tracking."""

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KobIntercompanyLoan(models.Model):
    _name = "kob.intercompany.loan"
    _description = "Intercompany Loan"
    _order = "issue_date desc"

    name = fields.Char(required=True, default=lambda s: _("New"), copy=False)
    lender_company_id = fields.Many2one("res.company", required=True)
    borrower_company_id = fields.Many2one("res.company", required=True)
    currency_id = fields.Many2one(
        "res.currency", required=True,
        default=lambda s: s.env.company.currency_id,
    )
    principal = fields.Monetary(currency_field="currency_id", required=True)
    interest_rate_pct = fields.Float(digits=(6, 4))
    issue_date = fields.Date(required=True, default=fields.Date.context_today)
    maturity_date = fields.Date()
    term_months = fields.Integer(default=12)
    installments_count = fields.Integer(default=12)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("settled", "Settled"),
            ("defaulted", "Defaulted"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    outstanding_balance = fields.Monetary(
        currency_field="currency_id", readonly=True,
    )
    activated_at = fields.Datetime(readonly=True)
    settled_at = fields.Datetime(readonly=True)
    installment_ids = fields.One2many("kob.loan.installment", "loan_id")

    @api.constrains("lender_company_id", "borrower_company_id")
    def _check_companies(self):
        for l in self:
            if l.lender_company_id == l.borrower_company_id:
                raise UserError(_("Lender and borrower must differ."))

    def action_activate(self):
        for loan in self:
            if loan.state != "draft":
                raise UserError(_("Only draft loans can be activated."))
            # Auto-generate installments if none yet
            if not loan.installment_ids and loan.installments_count > 0:
                principal_per = round(
                    float(loan.principal) / loan.installments_count, 2,
                )
                for i in range(loan.installments_count):
                    self.env["kob.loan.installment"].create({
                        "loan_id": loan.id,
                        "due_date": (
                            (loan.issue_date or fields.Date.context_today(loan))
                            + relativedelta(months=i + 1)
                        ),
                        "principal_due": principal_per,
                        "interest_due": round(
                            float(loan.principal)
                            * float(loan.interest_rate_pct or 0)
                            / 100.0 / 12.0,
                            2,
                        ),
                    })
            loan.write({
                "state": "active",
                "outstanding_balance": loan.principal,
                "activated_at": fields.Datetime.now(),
            })

    def repay_installment(self, installment, paid_amount, paid_date=None):
        """Apply payment to one installment."""
        self.ensure_one()
        if self.state != "active":
            raise UserError(_("Loan is not active."))
        installment.paid_amount = float(installment.paid_amount or 0) + float(
            paid_amount,
        )
        installment.paid_date = paid_date or fields.Date.context_today(self)
        total_due = installment.principal_due + installment.interest_due
        if installment.paid_amount >= total_due:
            installment.state = "paid" if (
                abs(installment.paid_amount - total_due) < 0.01
            ) else "overpaid"
        else:
            installment.state = "partial"
        # Recompute outstanding
        paid_total = sum(self.installment_ids.mapped("paid_amount"))
        self.outstanding_balance = max(0.0, float(self.principal) - paid_total)
        if self.outstanding_balance <= 0.01:
            self.write({
                "state": "settled",
                "settled_at": fields.Datetime.now(),
            })
        return installment


class KobLoanInstallment(models.Model):
    _name = "kob.loan.installment"
    _description = "Loan Installment"
    _order = "loan_id, due_date"

    loan_id = fields.Many2one(
        "kob.intercompany.loan", required=True, ondelete="cascade",
    )
    due_date = fields.Date(required=True)
    principal_due = fields.Monetary(currency_field="currency_id")
    interest_due = fields.Monetary(currency_field="currency_id")
    paid_amount = fields.Monetary(currency_field="currency_id")
    paid_date = fields.Date()
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("partial", "Partial"),
            ("paid", "Paid"),
            ("overpaid", "Overpaid"),
        ],
        default="pending",
    )
    currency_id = fields.Many2one(
        related="loan_id.currency_id", store=True, readonly=True,
    )

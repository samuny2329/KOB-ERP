# -*- coding: utf-8 -*-
"""SSO registration + monthly contribution Odoo models."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .services import compute_sso_amounts


class KobSsoRegistration(models.Model):
    """Thai Social Security registration for an Odoo HR employee."""

    _name = "kob.sso.registration"
    _description = "Thai SSO Registration"
    _sql_constraints = [
        ("ssn_unique", "unique(ssn)", "SSN must be unique."),
        ("employee_unique", "unique(employee_id)",
         "An employee can only have one active SSO registration."),
    ]

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, ondelete="cascade",
        index=True,
    )
    ssn = fields.Char(string="Social Security Number", required=True, size=20)
    registered_date = fields.Date(required=True, default=fields.Date.context_today)
    branch_code = fields.Char(string="SSO Branch")
    insured_type = fields.Selection(
        [
            ("article33", "Article 33 (Salaried)"),
            ("article39", "Article 39 (Voluntary)"),
            ("article40", "Article 40 (Informal)"),
        ],
        default="article33",
        required=True,
    )
    active = fields.Boolean(default=True)


class KobSsoContribution(models.Model):
    """One monthly SSO contribution row per employee per period."""

    _name = "kob.sso.contribution"
    _description = "Monthly SSO Contribution"
    _order = "period_year desc, period_month desc, employee_id"
    _sql_constraints = [
        (
            "uniq_period",
            "unique(company_id, employee_id, period_year, period_month)",
            "Contribution already exists for this employee and period.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
        index=True,
    )
    employee_id = fields.Many2one(
        "hr.employee", required=True, ondelete="cascade", index=True,
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    gross_wage = fields.Monetary(required=True, currency_field="currency_id")
    employee_amount = fields.Monetary(
        compute="_compute_amounts", store=True, currency_field="currency_id",
    )
    employer_amount = fields.Monetary(
        compute="_compute_amounts", store=True, currency_field="currency_id",
    )
    paid_at = fields.Datetime()
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )

    @api.depends("gross_wage")
    def _compute_amounts(self):
        for rec in self:
            emp, er = compute_sso_amounts(rec.gross_wage or 0)
            rec.employee_amount = emp
            rec.employer_amount = er

    @api.constrains("period_month", "period_year")
    def _check_period(self):
        for rec in self:
            if not (1 <= rec.period_month <= 12):
                raise UserError(_("period_month must be between 1 and 12."))
            if not (2000 <= rec.period_year <= 2100):
                raise UserError(_("period_year out of range."))

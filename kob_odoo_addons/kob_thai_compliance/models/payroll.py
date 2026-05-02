# -*- coding: utf-8 -*-
"""KOB Payroll — Thai-compliant payslip + batch + annual income tax cert.

Builds on existing kob.sso.contribution + kob.pnd.filing + kob.overtime.record.

Models:
  - kob.payslip          : per-employee per-month payslip
  - kob.payroll.batch    : monthly wrapper grouping payslips
  - kob.tax.cert.annual  : annual income tax cert (ภงด.91)
"""

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


# ───────────────────────────── Payslip ─────────────────────────────
class KobPayslip(models.Model):
    _name = "kob.payslip"
    _description = "KOB Payslip (monthly)"
    _order = "period_year desc, period_month desc, employee_id"
    _sql_constraints = [
        (
            "uniq_employee_period",
            "unique(employee_id, period_year, period_month)",
            "Payslip already exists for this employee and period.",
        ),
    ]

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee", required=True, ondelete="restrict", index=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    batch_id = fields.Many2one(
        "kob.payroll.batch", ondelete="cascade", index=True,
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("calculated", "Calculated"),
            ("approved", "Approved"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    # ── Earnings ──
    base_salary = fields.Monetary(
        currency_field="currency_id",
        help="Monthly base salary (gross). Source: hr.employee.contract or "
             "manual entry.",
    )
    ot_amount = fields.Monetary(
        currency_field="currency_id",
        help="Sum of overtime pay for the period — auto-pulled from "
             "kob.overtime.record entries dated in this month.",
    )
    bonus = fields.Monetary(
        currency_field="currency_id",
        help="Discretionary bonus / commission for this period.",
    )
    allowance = fields.Monetary(
        currency_field="currency_id",
        help="Fixed allowances (transport, meal, telephone).",
    )
    gross_pay = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="base_salary + ot_amount + bonus + allowance (taxable income "
             "before deductions).",
    )
    # ── Deductions ──
    sso_employee = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="Employee SSO contribution: min(gross × 5%, 750 ฿). "
             "Capped per Thai SSO Article 33.",
    )
    sso_employer = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="Employer SSO contribution: same formula as employee. "
             "Recorded but NOT deducted from net pay (cost to employer).",
    )
    wht_pnd1 = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="PND1 withholding tax — progressive monthly estimate based "
             "on annualized gross. Brackets: 0-150k=0%, 150-300k=5%, "
             "300-500k=10%, 500k-750k=15%, 750k-1M=20%, 1-2M=25%, "
             "2-5M=30%, 5M+=35%.",
    )
    other_deduction = fields.Monetary(
        currency_field="currency_id",
        help="Loans, advances, court orders, union dues, etc.",
    )
    net_pay = fields.Monetary(
        currency_field="currency_id", compute="_compute_amounts", store=True,
        help="gross_pay − sso_employee − wht_pnd1 − other_deduction. "
             "Amount paid to employee bank account.",
    )
    note = fields.Text()

    # ── compute name ──
    @api.depends("employee_id", "period_year", "period_month")
    def _compute_name(self):
        for r in self:
            r.name = (
                f"PAY/{r.period_year}/{r.period_month:02d}/{r.employee_id.name or '?'}"
            )

    # ── compute amounts ──
    @api.depends(
        "base_salary", "ot_amount", "bonus", "allowance", "other_deduction",
    )
    def _compute_amounts(self):
        for r in self:
            gross = float(r.base_salary or 0) + float(r.ot_amount or 0) + \
                    float(r.bonus or 0) + float(r.allowance or 0)
            r.gross_pay = gross
            # SSO 5% capped 750
            sso = min(gross * 0.05, 750.0)
            r.sso_employee = sso
            r.sso_employer = sso
            # PND1 WHT — progressive monthly approximation
            annual = gross * 12.0
            taxable = max(0.0, annual - 60000.0 - sso * 12.0)  # personal + SSO deduction
            tax = 0.0
            for low, high, rate in [
                (0, 150_000, 0.0),
                (150_000, 300_000, 0.05),
                (300_000, 500_000, 0.10),
                (500_000, 750_000, 0.15),
                (750_000, 1_000_000, 0.20),
                (1_000_000, 2_000_000, 0.25),
                (2_000_000, 5_000_000, 0.30),
                (5_000_000, 10**12, 0.35),
            ]:
                if taxable > low:
                    tax += (min(taxable, high) - low) * rate
            r.wht_pnd1 = round(tax / 12.0, 2)
            r.net_pay = gross - sso - r.wht_pnd1 - float(r.other_deduction or 0)

    # ── actions ──
    def action_calculate(self):
        for r in self:
            if r.state not in ("draft", "calculated"):
                raise UserError(_("Cannot recalculate in state %s.") % r.state)
            # Pull OT from kob.overtime.record
            ot_recs = self.env["kob.overtime.record"].search([
                ("employee_id", "=", r.employee_id.id),
                ("work_date", ">=", date(r.period_year, r.period_month, 1)),
                ("work_date", "<", (date(r.period_year, r.period_month, 1)
                                 + relativedelta(months=1))),
            ])
            r.ot_amount = sum(ot_recs.mapped("total_amount"))
            # Trigger compute
            r._compute_amounts()
            r.state = "calculated"

    def action_approve(self):
        for r in self:
            if r.state != "calculated":
                raise UserError(_("Only calculated payslips can be approved."))
            r.state = "approved"

    def action_pay(self):
        for r in self:
            if r.state != "approved":
                raise UserError(_("Only approved payslips can be paid."))
            r.state = "paid"


# ───────────────────────────── Batch ─────────────────────────────
class KobPayrollBatch(models.Model):
    _name = "kob.payroll.batch"
    _description = "Monthly Payroll Batch"
    _order = "period_year desc, period_month desc"
    _sql_constraints = [
        (
            "uniq_period",
            "unique(company_id, period_year, period_month)",
            "Payroll batch already exists for this period.",
        ),
    ]

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    period_year = fields.Integer(required=True)
    period_month = fields.Integer(required=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("generated", "Generated"),
            ("approved", "Approved"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    payslip_ids = fields.One2many("kob.payslip", "batch_id")
    # Totals
    total_gross = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True,
        help="Sum of gross pay across all payslips in this batch.",
    )
    total_sso = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True,
        help="Total SSO contribution (employee side) — payable to "
             "Social Security Office on the 15th of next month.",
    )
    total_wht = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True,
        help="Total PND1 withholding — payable to Revenue Department "
             "by the 7th of next month.",
    )
    total_net = fields.Monetary(
        currency_field="currency_id", compute="_compute_totals", store=True,
        help="Total cash to employees (gross − SSO − WHT − other deductions).",
    )

    @api.depends("period_year", "period_month")
    def _compute_name(self):
        for b in self:
            b.name = f"PAYROLL/{b.period_year}/{b.period_month:02d}"

    @api.depends(
        "payslip_ids.gross_pay", "payslip_ids.sso_employee",
        "payslip_ids.wht_pnd1", "payslip_ids.net_pay",
    )
    def _compute_totals(self):
        for b in self:
            b.total_gross = sum(b.payslip_ids.mapped("gross_pay"))
            b.total_sso = sum(b.payslip_ids.mapped("sso_employee"))
            b.total_wht = sum(b.payslip_ids.mapped("wht_pnd1"))
            b.total_net = sum(b.payslip_ids.mapped("net_pay"))

    def action_generate(self):
        """Create draft kob.payslip for every active employee."""
        for b in self:
            if b.state != "draft":
                raise UserError(_("Already generated."))
            employees = self.env["hr.employee"].search([
                ("active", "=", True),
                ("company_id", "=", b.company_id.id),
            ])
            for emp in employees:
                if emp.payslip_ids.filtered(
                    lambda p, b=b: p.period_year == b.period_year
                                and p.period_month == b.period_month,
                ):
                    continue
                # Try to fetch base salary from contract
                base = float(emp.contract_id.wage or 0) if emp.contract_id else 0
                self.env["kob.payslip"].create({
                    "employee_id": emp.id,
                    "company_id": b.company_id.id,
                    "batch_id": b.id,
                    "period_year": b.period_year,
                    "period_month": b.period_month,
                    "base_salary": base,
                })
            b.state = "generated"

    def action_calculate_all(self):
        for b in self:
            b.payslip_ids.action_calculate()

    def action_approve_all(self):
        for b in self:
            b.payslip_ids.filtered(
                lambda p: p.state == "calculated",
            ).action_approve()
            b.state = "approved"

    def action_pay_all(self):
        for b in self:
            b.payslip_ids.filtered(
                lambda p: p.state == "approved",
            ).action_pay()
            b.state = "paid"


# ───────────────────────── Annual Tax Cert (ภงด.91) ─────────────────
class KobTaxCertAnnual(models.Model):
    _name = "kob.tax.cert.annual"
    _description = "Annual Personal Income Tax Certificate (ภงด.91)"
    _order = "tax_year desc, employee_id"
    _sql_constraints = [
        (
            "uniq_employee_year",
            "unique(employee_id, tax_year)",
            "Tax cert already exists for this employee/year.",
        ),
    ]

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee", required=True, ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    tax_year = fields.Integer(
        required=True, default=lambda s: date.today().year,
        help="Calendar tax year (Buddhist calendar year not used).",
    )
    annual_gross = fields.Monetary(
        currency_field="currency_id",
        help="Sum of 12 monthly gross_pay from kob.payslip.",
    )
    deduction_personal = fields.Monetary(
        currency_field="currency_id", default=60000,
        help="Personal deduction (60,000 ฿ for 2026).",
    )
    deduction_sso = fields.Monetary(
        currency_field="currency_id",
        help="Sum of 12 monthly SSO contributions (capped 9,000 ฿/yr).",
    )
    deduction_other = fields.Monetary(
        currency_field="currency_id",
        help="Other allowances: spouse 60k, children 30k each, parents "
             "30k each, life insurance ≤ 100k, RMF/SSF, donation, etc.",
    )
    taxable_income = fields.Monetary(
        currency_field="currency_id", compute="_compute_tax", store=True,
    )
    tax_payable = fields.Monetary(
        currency_field="currency_id", compute="_compute_tax", store=True,
    )
    tax_withheld = fields.Monetary(
        currency_field="currency_id",
        help="Sum of 12 monthly wht_pnd1 from kob.payslip.",
    )
    refund_or_due = fields.Monetary(
        currency_field="currency_id", compute="_compute_tax", store=True,
        help="Positive = refund due to employee; Negative = additional tax owed.",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("calculated", "Calculated"),
            ("submitted", "Submitted to RD"),
        ],
        default="draft",
    )
    note = fields.Text()

    @api.depends("employee_id", "tax_year")
    def _compute_name(self):
        for r in self:
            r.name = f"PND91/{r.tax_year}/{r.employee_id.name or '?'}"

    @api.depends("annual_gross", "deduction_personal", "deduction_sso",
                 "deduction_other", "tax_withheld")
    def _compute_tax(self):
        for r in self:
            taxable = max(
                0.0,
                float(r.annual_gross or 0)
                - float(r.deduction_personal or 0)
                - float(r.deduction_sso or 0)
                - float(r.deduction_other or 0),
            )
            r.taxable_income = taxable
            tax = 0.0
            for low, high, rate in [
                (0, 150_000, 0.0),
                (150_000, 300_000, 0.05),
                (300_000, 500_000, 0.10),
                (500_000, 750_000, 0.15),
                (750_000, 1_000_000, 0.20),
                (1_000_000, 2_000_000, 0.25),
                (2_000_000, 5_000_000, 0.30),
                (5_000_000, 10**12, 0.35),
            ]:
                if taxable > low:
                    tax += (min(taxable, high) - low) * rate
            r.tax_payable = round(tax, 2)
            r.refund_or_due = float(r.tax_withheld or 0) - r.tax_payable

    def action_calculate(self):
        for r in self:
            slips = self.env["kob.payslip"].search([
                ("employee_id", "=", r.employee_id.id),
                ("period_year", "=", r.tax_year),
                ("state", "in", ("approved", "paid")),
            ])
            r.annual_gross = sum(slips.mapped("gross_pay"))
            sso = sum(slips.mapped("sso_employee"))
            r.deduction_sso = min(sso, 9000.0)
            r.tax_withheld = sum(slips.mapped("wht_pnd1"))
            r._compute_tax()
            r.state = "calculated"

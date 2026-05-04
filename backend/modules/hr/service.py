"""HR business logic — Thai SSO, PVD, progressive income tax, payslip computation."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.workflow import WorkflowError
from backend.modules.hr.models import Employee, Payslip, PayslipLine, SalaryRule, SalaryStructure
from backend.modules.hr.models_advanced import (
    Contract,
    Expense,
    OvertimeRequest,
    ProvidentFund,
    ProvidentFundMember,
    ThaiPnd1Line,
    ThaiSsoRecord,
)


# ── Thai SSO (ประกันสังคม) ─────────────────────────────────────────────


SSO_MAX_BASE = 15_000.0   # max contributory wage
SSO_MAX_AMOUNT = 750.0    # 5% × 15,000
SSO_RATE = 5.0


def compute_thai_sso(gross_income: float, rate_pct: float = SSO_RATE) -> dict[str, float]:
    """Compute SSO contribution (capped at 750 THB/month for each side).

    Returns: {sso_base, rate_pct, sso_amount, employer_amount}
    """
    base = min(gross_income, SSO_MAX_BASE)
    amount = round(base * rate_pct / 100, 2)
    amount = min(amount, SSO_MAX_AMOUNT)
    return {
        "sso_base": round(base, 2),
        "rate_pct": rate_pct,
        "sso_amount": amount,
        "employer_amount": amount,
    }


# ── Provident Fund (กองทุนสำรองเลี้ยงชีพ) ────────────────────────────


def compute_provident_fund(
    gross_income: float,
    employee_rate_pct: float,
    employer_rate_pct: float,
) -> dict[str, float]:
    """Compute monthly PVD contributions (both sides)."""
    employee = round(gross_income * employee_rate_pct / 100, 2)
    employer = round(gross_income * employer_rate_pct / 100, 2)
    return {"contribution_employee": employee, "contribution_employer": employer}


# ── Thai Progressive Income Tax ────────────────────────────────────────

# Brackets: (upper_limit, rate_pct)  — annual income in THB
_TAX_BRACKETS = [
    (150_000, 0.0),
    (300_000, 5.0),
    (500_000, 10.0),
    (750_000, 15.0),
    (1_000_000, 20.0),
    (2_000_000, 25.0),
    (5_000_000, 30.0),
    (float("inf"), 35.0),
]

# Standard deduction: 50% of income, max 100,000; personal exemption 60,000
_PERSONAL_EXEMPTION = 60_000.0
_EXPENSE_DEDUCTION_RATE = 0.50
_EXPENSE_DEDUCTION_MAX = 100_000.0


def compute_progressive_tax(annual_income: float) -> dict[str, float]:
    """Thai personal income tax — progressive brackets per RD 2024.

    Deductions applied: 50% expense (max 100k) + 60k personal exemption.
    Returns: {annual_income, net_income, annual_tax, monthly_tax}
    """
    expense_deduction = min(annual_income * _EXPENSE_DEDUCTION_RATE, _EXPENSE_DEDUCTION_MAX)
    net_income = max(0.0, annual_income - expense_deduction - _PERSONAL_EXEMPTION)

    tax = 0.0
    prev_limit = 0.0
    for upper, rate in _TAX_BRACKETS:
        if net_income <= prev_limit:
            break
        taxable_in_band = min(net_income, upper) - prev_limit
        tax += taxable_in_band * rate / 100
        prev_limit = upper

    monthly_tax = round(tax / 12, 2)
    return {
        "annual_income": round(annual_income, 2),
        "net_income": round(net_income, 2),
        "annual_tax": round(tax, 2),
        "monthly_tax": monthly_tax,
    }


def compute_monthly_wht(monthly_income: float) -> float:
    """Estimate monthly income tax withholding from monthly gross pay."""
    return compute_progressive_tax(monthly_income * 12)["monthly_tax"]


# ── Payslip Computation ────────────────────────────────────────────────


async def compute_payslip(
    session: AsyncSession,
    payslip: Payslip,
) -> Payslip:
    """Compute all payslip lines from salary structure + Thai statutory deductions."""
    employee = await session.get(Employee, payslip.employee_id)
    if not employee:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")

    # Load salary structure rules
    structure = await session.get(
        SalaryStructure, payslip.structure_id, options=[selectinload(SalaryStructure.rules)]
    )
    if not structure:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "salary structure not found")

    basic = float(payslip.basic_salary)
    total_allowances = 0.0
    total_deductions = 0.0

    # Delete existing lines to recompute
    from sqlalchemy import delete
    await session.execute(delete(PayslipLine).where(PayslipLine.payslip_id == payslip.id))

    for rule in sorted(structure.rules, key=lambda r: r.sequence):
        if rule.amount_type == "fixed":
            amount = float(rule.amount)
        elif rule.amount_type == "percentage":
            amount = round(basic * float(rule.rate_pct) / 100, 2)
        else:
            amount = 0.0

        session.add(PayslipLine(
            payslip_id=payslip.id,
            rule_id=rule.id,
            name=rule.name,
            rule_type=rule.rule_type,
            amount=amount,
        ))

        if rule.rule_type == "allowance":
            total_allowances += amount
        elif rule.rule_type == "deduction":
            total_deductions += amount

    gross = basic + total_allowances

    # Thai SSO
    sso = compute_thai_sso(gross)
    payslip.sso_employee = sso["sso_amount"]
    payslip.sso_employer = sso["employer_amount"]

    # PVD (if enrolled)
    pvd_employee = 0.0
    pvd_employer = 0.0
    if employee.provident_fund_id:
        fund = await session.get(ProvidentFund, employee.provident_fund_id)
        if fund:
            pvd = compute_provident_fund(gross, float(fund.employee_rate_pct), float(fund.employer_rate_pct))
            pvd_employee = pvd["contribution_employee"]
            pvd_employer = pvd["contribution_employer"]
    payslip.provident_fund_employee = pvd_employee
    payslip.provident_fund_employer = pvd_employer

    # Monthly income tax
    monthly_wht = compute_monthly_wht(gross)
    payslip.income_tax = monthly_wht

    total_deductions += sso["sso_amount"] + pvd_employee + monthly_wht
    payslip.total_allowances = round(total_allowances, 2)
    payslip.total_deductions = round(total_deductions, 2)
    payslip.net_salary = round(gross - sso["sso_amount"] - pvd_employee, 2)
    payslip.net_after_tax = round(gross - sso["sso_amount"] - pvd_employee - monthly_wht, 2)

    await session.flush()
    return payslip


# ── PND1 Line Generation ────────────────────────────────────────────────


async def generate_pnd1_lines(
    session: AsyncSession,
    company_id: int,
    period_month: int,
    period_year: int,
) -> list[ThaiPnd1Line]:
    """Generate ภงด.1 lines from confirmed payslips for the period."""
    from sqlalchemy import extract

    payslips_result = await session.execute(
        select(Payslip)
        .join(Employee, Employee.id == Payslip.employee_id)
        .where(
            Employee.company_id == company_id,
            Payslip.state == "confirmed",
            Payslip.deleted_at.is_(None),
            extract("month", Payslip.period_from) == period_month,
            extract("year", Payslip.period_from) == period_year,
        )
    )
    payslips = list(payslips_result.scalars().all())

    lines = []
    for ps in payslips:
        gross = float(ps.basic_salary) + float(ps.total_allowances)
        wht = float(ps.income_tax)

        existing = (
            await session.execute(
                select(ThaiPnd1Line).where(
                    ThaiPnd1Line.employee_id == ps.employee_id,
                    ThaiPnd1Line.payslip_id == ps.id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            lines.append(existing)
            continue

        line = ThaiPnd1Line(
            employee_id=ps.employee_id,
            payslip_id=ps.id,
            period_month=period_month,
            period_year=period_year,
            taxable_income=round(gross, 2),
            cumulative_income=round(gross, 2),
            wht_amount=round(wht, 2),
            wht_method="progressive",
        )
        session.add(line)
        lines.append(line)

    await session.flush()
    return lines


# ── Expense & OT Workflows ─────────────────────────────────────────────


async def approve_expense(session: AsyncSession, expense: Expense, approver_id: int) -> Expense:
    """submitted → approved."""
    try:
        expense.transition("approved")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    expense.approved_by_id = approver_id
    expense.approved_at = datetime.now(UTC)
    await session.flush()
    return expense


async def approve_overtime(session: AsyncSession, ot: OvertimeRequest, approver_id: int) -> OvertimeRequest:
    """draft → approved."""
    try:
        ot.transition("approved")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    ot.approved_by_id = approver_id
    ot.approved_at = datetime.now(UTC)
    await session.flush()
    return ot

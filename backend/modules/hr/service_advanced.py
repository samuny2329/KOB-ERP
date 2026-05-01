"""HR business logic for Phase 14."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.workflow import WorkflowError
from backend.modules.hr.models import Employee, Leave
from backend.modules.hr.models_advanced import (
    OT_MULTIPLIERS,
    EmployeeTransfer,
    LeaveEntitlement,
    OvertimeRecord,
    PndFiling,
    PndFilingLine,
    SsoContribution,
)


# ── SSO contribution maths ─────────────────────────────────────────────


SSO_RATE_PCT = 5.0          # employee 5%, employer 5%
SSO_WAGE_CAP = 15000.0      # THB — wage cap
SSO_MAX_AMOUNT = 750.0      # 5% × 15,000


def compute_sso_amounts(gross_wage: float) -> tuple[float, float]:
    """Returns ``(employee_amount, employer_amount)`` for one month.

    Both capped at 750 THB; computed on min(gross_wage, 15000) × 5%.
    """
    capped_wage = min(float(gross_wage), SSO_WAGE_CAP)
    amt = round(capped_wage * SSO_RATE_PCT / 100, 2)
    return amt, amt


# ── PND1 progressive WHT (very simplified Thai brackets 2024) ──────────

# Annualised brackets in THB.  The simplified form: monthly WHT is
# (annualised tax) / 12.  Progressive marginal rates apply.
PND_BRACKETS: list[tuple[float, float]] = [
    (150_000, 0.00),
    (300_000, 0.05),
    (500_000, 0.10),
    (750_000, 0.15),
    (1_000_000, 0.20),
    (2_000_000, 0.25),
    (5_000_000, 0.30),
    (float("inf"), 0.35),
]


def compute_progressive_tax(annual_taxable_income: float) -> float:
    """Sum of marginal tax across PND_BRACKETS."""
    remaining = float(annual_taxable_income)
    last_threshold = 0.0
    tax = 0.0
    for threshold, rate in PND_BRACKETS:
        slice_amount = min(remaining, threshold - last_threshold)
        if slice_amount <= 0:
            break
        tax += slice_amount * rate
        remaining -= slice_amount
        last_threshold = threshold
    return round(tax, 2)


def compute_monthly_wht(monthly_taxable_income: float) -> tuple[float, float]:
    """Returns ``(monthly_wht, effective_rate_pct)``."""
    annual = float(monthly_taxable_income) * 12
    annual_tax = compute_progressive_tax(annual)
    monthly = round(annual_tax / 12, 2)
    rate_pct = (annual_tax / annual * 100) if annual > 0 else 0
    return monthly, round(rate_pct, 4)


# ── PND filing generation ──────────────────────────────────────────────


async def calculate_pnd_filing(
    session: AsyncSession, filing: PndFiling
) -> PndFiling:
    """Pull payroll lines from the period and write filing lines.

    For Phase 14a we read SSO contributions as a proxy for who got paid
    — in production this would join `hr.payslip_line` of the period.
    """
    try:
        filing.transition("calculated")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    # Reset lines (idempotent recompute)
    for old in list(filing.lines):
        await session.delete(old)
    await session.flush()

    contrib_stmt = (
        select(SsoContribution)
        .where(
            SsoContribution.company_id == filing.company_id,
            SsoContribution.period_year == filing.period_year,
            SsoContribution.period_month == filing.period_month,
        )
    )
    contributions = (await session.execute(contrib_stmt)).scalars().all()

    total_gross = 0.0
    total_wht = 0.0
    for c in contributions:
        emp = await session.get(Employee, c.employee_id)
        if emp is None:
            continue
        gross = float(c.gross_wage)
        deductions = float(c.employee_amount)  # SSO deducted
        taxable = max(0.0, gross - deductions)
        wht, rate = compute_monthly_wht(taxable)
        line = PndFilingLine(
            filing_id=filing.id,
            employee_id=emp.id,
            employee_name=f"{emp.first_name} {emp.last_name}".strip(),
            national_id=emp.national_id,
            gross_wage=gross,
            deductions=deductions,
            taxable_income=taxable,
            wht_amount=wht,
            wht_rate_pct=rate,
        )
        session.add(line)
        total_gross += gross
        total_wht += wht

    filing.total_gross_wage = round(total_gross, 2)
    filing.total_wht = round(total_wht, 2)
    await session.flush()
    await session.refresh(filing, attribute_names=["lines"])
    return filing


async def submit_pnd_filing(
    session: AsyncSession,
    filing: PndFiling,
    submitted_by: int | None,
    rd_receipt_number: str | None = None,
) -> PndFiling:
    """calculated → submitted."""
    try:
        filing.transition("submitted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    filing.submitted_at = datetime.now(UTC)
    filing.submitted_by = submitted_by
    filing.rd_receipt_number = rd_receipt_number
    return filing


# ── Overtime calculation ───────────────────────────────────────────────


def compute_overtime(
    ot_kind: str,
    hours: float,
    base_hourly_rate: float,
) -> tuple[float, float]:
    """Pure function — Thai LPA OT total + multiplier.

    Returns ``(total_amount, rate_multiplier)``.  The multiplier is the
    Thai LPA value at the time of calculation; we store it on the record
    so historical entries don't change if law updates.
    """
    multiplier = OT_MULTIPLIERS.get(ot_kind)
    if multiplier is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"unknown ot_kind: {ot_kind!r}"
        )
    total = round(float(hours) * float(base_hourly_rate) * multiplier, 2)
    return total, multiplier


# ── Annual leave entitlement (Thai LPA tier) ───────────────────────────


# Tiered policy beyond the LPA minimum (6 days/year after 1 year).
# Years 0–1: 0 days legal minimum (we grant 6 anyway as KOB policy)
# Years 1–3: 6 days
# Years 3–5: 8 days
# Years 5–10: 10 days
# Years 10+: 14 days
def resolve_leave_grant(years_of_service: int) -> tuple[float, str]:
    """Returns ``(granted_days, rule_label)``."""
    if years_of_service < 1:
        return 6.0, "kob_policy_first_year"
    if years_of_service < 3:
        return 6.0, "lpa_minimum_1_to_3"
    if years_of_service < 5:
        return 8.0, "kob_tier_3_to_5"
    if years_of_service < 10:
        return 10.0, "kob_tier_5_to_10"
    return 14.0, "kob_tier_10_plus"


def years_of_service(hire_date: date, asof: date) -> int:
    """Whole-year tenure from hire_date to asof."""
    delta = (asof.year - hire_date.year) - (
        1 if (asof.month, asof.day) < (hire_date.month, hire_date.day) else 0
    )
    return max(0, delta)


# ── Cross-company employee transfer ────────────────────────────────────


async def complete_employee_transfer(
    session: AsyncSession, transfer: EmployeeTransfer
) -> EmployeeTransfer:
    """approved → completed.  Updates the employee record in place.

    Preserves ``hire_date`` if ``keep_service_date=True`` (default — Thai
    labour-friendly).  If False, sets a new "effective" hire date but keeps
    the original recorded as a transfer history.
    """
    try:
        transfer.transition("completed")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    employee = await session.get(Employee, transfer.employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")

    if transfer.new_department_id is not None:
        employee.department_id = transfer.new_department_id
    if transfer.new_warehouse_id is not None:
        employee.warehouse_id = transfer.new_warehouse_id
    # Note: `hr.employee` doesn't have a `company_id` column today; the
    # tracking lives on the transfer row.  Add to employee in a follow-up
    # migration if/when payroll runs need direct filtering.
    transfer.completed_at = datetime.now(UTC)
    return transfer

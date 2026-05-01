"""HR advanced — Thai-specific compliance models.

Covers things every Thai SME deals with monthly/annually:
  * Social Security (SSO) registration + contributions (5% employee + 5% employer)
  * PND1 monthly WHT filing for salaries
  * Overtime under Labor Protection Act (1.5× weekday, 3× holiday, 1× rest day)
  * Annual leave entitlement auto-accrued per Thai LPA tier
  * Cross-company employee transfer preserving service + leave balance

All filings carry ``company_id`` so multi-co payroll consolidation works.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


# ── Social Security (SSO) ──────────────────────────────────────────────


class SsoRegistration(BaseModel):
    """Per-employee SSO registration data.

    Required by Thai law for full-time employees.  ``ssn`` is the SSO
    insured-person number (13 digits, distinct from national_id).
    """

    __tablename__ = "sso_registration"
    __table_args__ = (
        UniqueConstraint("employee_id", name="uq_sso_employee"),
        {"schema": "hr"},
    )

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ssn: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    registered_date: Mapped[date] = mapped_column(Date, nullable=False)
    branch_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    insured_type: Mapped[str] = mapped_column(String(10), default="article33", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SsoContribution(BaseModel):
    """Monthly SSO contribution per (employee, period).

    Thai rate: 5% of monthly wage, capped at 750 THB each side
    (so wage cap is 15,000 THB).  ``employee_amount`` and
    ``employer_amount`` are stored explicitly for audit.
    """

    __tablename__ = "sso_contribution"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "period_year", "period_month", name="uq_sso_contrib_period"
        ),
        {"schema": "hr"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_wage: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    employee_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    employer_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


# ── PND1 monthly WHT filing ────────────────────────────────────────────


class PndFiling(BaseModel, WorkflowMixin):
    """Monthly PND1 (ภงด.1) WHT filing per company.

    Aggregates per-employee tax withheld for that month.  State machine:
    draft → calculated → submitted → settled (terminal) plus cancelled.
    """

    __tablename__ = "pnd_filing"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "filing_type", "period_year", "period_month",
            name="uq_pnd_filing_period",
        ),
        {"schema": "hr"},
    )

    initial_state = "draft"
    allowed_transitions = {
        "draft": {"calculated", "cancelled"},
        "calculated": {"submitted", "draft", "cancelled"},
        "submitted": {"settled"},
        "settled": set(),
        "cancelled": set(),
    }

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    filing_type: Mapped[str] = mapped_column(String(20), default="pnd1", nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    total_gross_wage: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_wht: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    rd_receipt_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["PndFilingLine"]] = relationship(
        back_populates="filing", lazy="selectin", cascade="all, delete-orphan"
    )


class PndFilingLine(BaseModel):
    """One employee's row in a PND filing."""

    __tablename__ = "pnd_filing_line"
    __table_args__ = ({"schema": "hr"},)

    filing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.pnd_filing.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="RESTRICT"), nullable=False
    )
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gross_wage: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    deductions: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    taxable_income: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    wht_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    wht_rate_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0)

    filing: Mapped[PndFiling] = relationship(back_populates="lines", lazy="select")


# ── Overtime (Thai Labor Protection Act) ───────────────────────────────


# Multipliers per Thai LPA section 61-63
OT_KINDS = ("weekday_after_hours", "weekend_normal", "weekend_after_hours", "holiday")

OT_MULTIPLIERS: dict[str, float] = {
    "weekday_after_hours": 1.5,   # >8h on a normal working day
    "weekend_normal": 1.0,        # rest day, normal hours (paid +1× of base)
    "weekend_after_hours": 3.0,   # >8h on a rest day
    "holiday": 3.0,               # public-holiday work (any hours)
}


class OvertimeRecord(BaseModel, WorkflowMixin):
    """Overtime record with LPA-compliant multiplier.

    ``rate_multiplier`` is denormalised from ``OT_MULTIPLIERS[ot_kind]`` at
    record creation; if Thai law changes the multipliers later, historical
    records keep their original rates for audit.
    """

    __tablename__ = "overtime_record"
    __table_args__ = ({"schema": "hr"},)

    initial_state = "draft"
    allowed_transitions = {
        "draft": {"submitted", "cancelled"},
        "submitted": {"approved", "rejected", "draft"},
        "approved": {"paid"},
        "paid": set(),
        "rejected": set(),
        "cancelled": set(),
    }

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ot_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    base_hourly_rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    rate_multiplier: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


# ── Annual leave entitlement (per Thai LPA) ────────────────────────────


# Thai LPA section 30: minimum 6 working-days per year after 1 year of service.
# Common SME practice escalates by tenure; we store the resolved entitlement
# per (employee, year) so historical changes survive policy edits.


class LeaveEntitlement(BaseModel):
    """Per-employee annual leave entitlement snapshot.

    Refreshed by a yearly job — one row per (employee, year, leave_type).
    ``carried_over`` lets policies that allow ≤ N days roll-over track
    explicitly.
    """

    __tablename__ = "leave_entitlement"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "year", "leave_type_id", name="uq_leave_entitlement"
        ),
        {"schema": "hr"},
    )

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False
    )
    leave_type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.leave_type.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    granted_days: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    carried_over: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    used_days: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    remaining_days: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


# ── Cross-company employee transfer ────────────────────────────────────


class EmployeeTransfer(BaseModel, WorkflowMixin):
    """Move an employee between companies in the group, preserve service.

    Use case: KOB-Cosmetics employee moves to KOB-Distribution.  We don't
    create a new ``hr.employee`` row — instead we keep the same record and
    log this transfer so leave balance + tenure carry over.
    """

    __tablename__ = "employee_transfer"
    __table_args__ = ({"schema": "hr"},)

    initial_state = "pending"
    allowed_transitions = {
        "pending": {"approved", "cancelled"},
        "approved": {"completed"},
        "completed": set(),
        "cancelled": set(),
    }

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    to_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    new_position: Mapped[str | None] = mapped_column(String(120), nullable=True)
    new_department_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("hr.department.id", ondelete="SET NULL"), nullable=True
    )
    new_warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL"), nullable=True
    )
    salary_adjustment_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    keep_service_date: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    keep_leave_balance: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

"""Advanced HR models — contracts, appraisals, expenses, Thai SSO/PVD/PND1, shift roster."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


# ── Org Structure ──────────────────────────────────────────────────────


class JobPosition(BaseModel):
    """Defined job position in the org chart."""

    __tablename__ = "job_position"
    __table_args__ = ({"schema": "hr"},)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("hr.department.id", ondelete="SET NULL"), nullable=True
    )
    no_of_recruitment: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Contracts ──────────────────────────────────────────────────────────


class Contract(BaseModel, WorkflowMixin):
    """Employee employment contract."""

    __tablename__ = "contract"
    __table_args__ = ({"schema": "hr"},)

    allowed_transitions: dict = {
        "draft": {"running", "cancelled"},
        "running": {"expired", "cancelled"},
        "expired": set(),
        "cancelled": set(),
    }

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    structure_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.salary_structure.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    contract_type: Mapped[str] = mapped_column(String(30), default="permanent", nullable=False)
    wage: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── Appraisal ──────────────────────────────────────────────────────────


class Appraisal(BaseModel, WorkflowMixin):
    """Performance appraisal cycle."""

    __tablename__ = "appraisal"
    __table_args__ = ({"schema": "hr"},)

    allowed_transitions: dict = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    manager_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2025-H1"
    overall_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["AppraisalLine"]] = relationship(
        back_populates="appraisal", lazy="select", cascade="all, delete-orphan"
    )


class AppraisalLine(BaseModel):
    """Per-criteria scoring line inside an appraisal."""

    __tablename__ = "appraisal_line"
    __table_args__ = ({"schema": "hr"},)

    appraisal_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.appraisal.id", ondelete="CASCADE"), nullable=False
    )
    criteria: Mapped[str] = mapped_column(String(120), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    appraisal: Mapped[Appraisal] = relationship(back_populates="lines", lazy="select")


# ── Expenses ───────────────────────────────────────────────────────────


class Expense(BaseModel, WorkflowMixin):
    """Employee expense claim."""

    __tablename__ = "expense"
    __table_args__ = ({"schema": "hr"},)

    allowed_transitions: dict = {
        "draft": {"submitted", "cancelled"},
        "submitted": {"approved", "refused"},
        "approved": {"paid"},
        "paid": set(),
        "refused": set(),
        "cancelled": set(),
    }

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["ExpenseLine"]] = relationship(
        back_populates="expense", lazy="select", cascade="all, delete-orphan"
    )


class ExpenseLine(BaseModel):
    """Individual line item inside an expense claim."""

    __tablename__ = "expense_line"
    __table_args__ = ({"schema": "hr"},)

    expense_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.expense.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )

    expense: Mapped[Expense] = relationship(back_populates="lines", lazy="select")


# ── Training ───────────────────────────────────────────────────────────


class TrainingCourse(BaseModel):
    """Training course catalogue."""

    __tablename__ = "training_course"
    __table_args__ = ({"schema": "hr"},)

    name: Mapped[str] = mapped_column(String(240), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_hours: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    enrollments: Mapped[list["TrainingEnrollment"]] = relationship(
        back_populates="course", lazy="select", cascade="all, delete-orphan"
    )


class TrainingEnrollment(BaseModel):
    """Employee enrollment in a training course."""

    __tablename__ = "training_enrollment"
    __table_args__ = (
        UniqueConstraint("employee_id", "course_id", name="uq_training_enrollment"),
        {"schema": "hr"},
    )

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.training_course.id", ondelete="CASCADE"), nullable=False
    )
    enrolled_at: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="enrolled", nullable=False)

    course: Mapped[TrainingCourse] = relationship(back_populates="enrollments", lazy="select")


# ── KOB-Exclusive: Thai Payroll ────────────────────────────────────────


class ProvidentFund(BaseModel):
    """Registered provident fund (กองทุนสำรองเลี้ยงชีพ)."""

    __tablename__ = "provident_fund"
    __table_args__ = ({"schema": "hr"},)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    fund_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    employee_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=5.0, nullable=False)
    employer_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=5.0, nullable=False)
    fund_manager: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["ProvidentFundMember"]] = relationship(
        back_populates="fund", lazy="select", cascade="all, delete-orphan"
    )


class ProvidentFundMember(BaseModel):
    """Monthly PVD contribution record per employee."""

    __tablename__ = "provident_fund_member"
    __table_args__ = (
        UniqueConstraint("fund_id", "employee_id", "period_year", "period_month", name="uq_pvd_member_period"),
        {"schema": "hr"},
    )

    fund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.provident_fund.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    contribution_employee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    contribution_employer: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    fund: Mapped[ProvidentFund] = relationship(back_populates="members", lazy="select")


class ThaiSsoRecord(BaseModel):
    """Monthly Social Security Office (ประกันสังคม) contribution record."""

    __tablename__ = "thai_sso_record"
    __table_args__ = (
        UniqueConstraint("employee_id", "period_year", "period_month", name="uq_sso_employee_period"),
        {"schema": "hr"},
    )

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_income: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    sso_base: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)  # capped at 15,000
    sso_rate_pct: Mapped[float] = mapped_column(Numeric(4, 2), default=5.0, nullable=False)
    sso_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)  # employee share (max 750)
    employer_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class ThaiPnd1Line(BaseModel):
    """Per-employee WHT line for ภงด.1 monthly return."""

    __tablename__ = "thai_pnd1_line"
    __table_args__ = (
        UniqueConstraint("employee_id", "payslip_id", name="uq_pnd1_employee_payslip"),
        {"schema": "hr"},
    )

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payslip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.payslip.id", ondelete="CASCADE"), nullable=False
    )
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    taxable_income: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    cumulative_income: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    wht_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    wht_method: Mapped[str] = mapped_column(String(20), default="progressive", nullable=False)


# ── Shift Roster & Overtime ────────────────────────────────────────────


class ShiftRoster(BaseModel):
    """Employee shift assignment for a specific date."""

    __tablename__ = "shift_roster"
    __table_args__ = (
        UniqueConstraint("employee_id", "roster_date", name="uq_shift_roster_employee_date"),
        {"schema": "hr"},
    )

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shift_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mfg.production_shift.id", ondelete="SET NULL"), nullable=True
    )
    roster_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)


class OvertimeRequest(BaseModel, WorkflowMixin):
    """Employee overtime pre-approval request."""

    __tablename__ = "overtime_request"
    __table_args__ = ({"schema": "hr"},)

    allowed_transitions: dict = {
        "draft": {"approved", "rejected"},
        "approved": set(),
        "rejected": set(),
    }

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    ot_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[float] = mapped_column(Float, nullable=False)
    rate_multiplier: Mapped[float] = mapped_column(Float, default=1.5, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

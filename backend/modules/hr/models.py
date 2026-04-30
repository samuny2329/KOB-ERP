"""HR models — departments, employees, attendance, leave, payroll."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


class Department(BaseModel):
    """Organisational department."""

    __tablename__ = "department"
    __table_args__ = ({"schema": "hr"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("hr.department.id", ondelete="SET NULL")
    )
    manager_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    employees: Mapped[list["Employee"]] = relationship(
        "Employee",
        primaryjoin="Employee.department_id == Department.id",
        lazy="select",
    )


class Employee(BaseModel):
    """Employee record — links to system user optionally."""

    __tablename__ = "employee"
    __table_args__ = ({"schema": "hr"},)

    employee_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    nick_name: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    national_id: Mapped[str | None] = mapped_column(String(20))
    department_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("hr.department.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_title: Mapped[str | None] = mapped_column(String(120))
    hire_date: Mapped[date | None] = mapped_column(Date)
    termination_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL")
    )
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL")
    )

    department: Mapped[Department | None] = relationship(
        Department,
        foreign_keys=[department_id],
        back_populates="employees",
        lazy="select",
    )
    attendances: Mapped[list["Attendance"]] = relationship(
        back_populates="employee", lazy="select"
    )
    leaves: Mapped[list["Leave"]] = relationship(back_populates="employee", lazy="select")


class Attendance(BaseModel):
    """Daily clock-in / clock-out record."""

    __tablename__ = "attendance"
    __table_args__ = ({"schema": "hr"},)

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    check_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    work_location: Mapped[str | None] = mapped_column(String(120))
    worked_hours: Mapped[float | None] = mapped_column(Float)
    overtime_hours: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(String(240))

    employee: Mapped[Employee] = relationship(back_populates="attendances", lazy="select")


LEAVE_STATES = ["draft", "submitted", "approved", "rejected", "cancelled"]


class LeaveType(BaseModel):
    """Leave type catalogue (annual, sick, personal, etc.)."""

    __tablename__ = "leave_type"
    __table_args__ = ({"schema": "hr"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    max_days_per_year: Mapped[int] = mapped_column(Integer, default=0)
    paid: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Leave(BaseModel, WorkflowMixin):
    """Employee leave request."""

    __tablename__ = "leave"
    __table_args__ = ({"schema": "hr"},)

    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.leave_type.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    days_requested: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    approved_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employee: Mapped[Employee] = relationship(back_populates="leaves", lazy="select")


class SalaryStructure(BaseModel):
    """Payroll salary structure — defines allowances and deductions."""

    __tablename__ = "salary_structure"
    __table_args__ = ({"schema": "hr"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    rules: Mapped[list["SalaryRule"]] = relationship(
        back_populates="structure", lazy="select", cascade="all, delete-orphan"
    )


class SalaryRule(BaseModel):
    """Single computation rule within a salary structure."""

    __tablename__ = "salary_rule"
    __table_args__ = ({"schema": "hr"},)

    structure_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.salary_structure.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(20), default="allowance")
    amount_type: Mapped[str] = mapped_column(String(20), default="fixed")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    rate_pct: Mapped[float] = mapped_column(Float, default=0)
    sequence: Mapped[int] = mapped_column(Integer, default=10)

    structure: Mapped[SalaryStructure] = relationship(back_populates="rules", lazy="select")


PAYSLIP_STATES = ["draft", "confirmed", "paid", "cancelled"]


class Payslip(BaseModel, WorkflowMixin):
    """Monthly payslip for an employee."""

    __tablename__ = "payslip"
    __table_args__ = ({"schema": "hr"},)

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    structure_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.salary_structure.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    basic_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    total_allowances: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_deductions: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    net_salary: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["PayslipLine"]] = relationship(
        back_populates="payslip", lazy="select", cascade="all, delete-orphan"
    )


class PayslipLine(BaseModel):
    """Computed amount for one salary rule."""

    __tablename__ = "payslip_line"
    __table_args__ = ({"schema": "hr"},)

    payslip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.payslip.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hr.salary_rule.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(20), default="allowance")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    payslip: Mapped[Payslip] = relationship(back_populates="lines", lazy="select")

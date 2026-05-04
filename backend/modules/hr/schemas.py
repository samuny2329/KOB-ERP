"""Pydantic schemas for the HR module."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DepartmentCreate(_Base):
    code: str
    name: str
    parent_id: int | None = None


class DepartmentRead(_Base):
    id: int
    code: str
    name: str
    parent_id: int | None
    active: bool


class EmployeeCreate(_Base):
    employee_code: str
    first_name: str
    last_name: str
    nick_name: str | None = None
    email: str | None = None
    phone: str | None = None
    national_id: str | None = None
    department_id: int | None = None
    job_title: str | None = None
    hire_date: date | None = None
    warehouse_id: int | None = None
    user_id: int | None = None
    company_id: int | None = None
    manager_id: int | None = None
    job_position_id: int | None = None
    sso_number: str | None = None
    provident_fund_id: int | None = None


class EmployeeRead(_Base):
    id: int
    employee_code: str
    first_name: str
    last_name: str
    nick_name: str | None
    email: str | None
    phone: str | None
    department_id: int | None
    job_title: str | None
    hire_date: date | None
    active: bool
    company_id: int | None
    manager_id: int | None
    job_position_id: int | None
    sso_number: str | None
    provident_fund_id: int | None


class AttendanceCreate(_Base):
    employee_id: int
    check_in: datetime
    check_out: datetime | None = None
    work_location: str | None = None
    notes: str | None = None


class AttendanceRead(_Base):
    id: int
    employee_id: int
    check_in: datetime
    check_out: datetime | None
    worked_hours: float | None
    overtime_hours: float


class LeaveTypeCreate(_Base):
    code: str
    name: str
    max_days_per_year: int = 0
    paid: bool = True


class LeaveTypeRead(_Base):
    id: int
    code: str
    name: str
    max_days_per_year: int
    paid: bool


class LeaveCreate(_Base):
    employee_id: int
    leave_type_id: int
    date_from: date
    date_to: date
    days_requested: float
    reason: str | None = None


class LeaveRead(_Base):
    id: int
    employee_id: int
    leave_type_id: int
    state: str
    date_from: date
    date_to: date
    days_requested: float
    reason: str | None


class SalaryRuleCreate(_Base):
    code: str
    name: str
    rule_type: str = "allowance"
    amount_type: str = "fixed"
    amount: float = 0
    rate_pct: float = 0
    sequence: int = 10


class SalaryStructureCreate(_Base):
    code: str
    name: str
    rules: list[SalaryRuleCreate] = []


class SalaryStructureRead(_Base):
    id: int
    code: str
    name: str
    active: bool


class PayslipLineRead(_Base):
    id: int
    name: str
    rule_type: str
    amount: float


class PayslipCreate(_Base):
    number: str
    employee_id: int
    structure_id: int
    period_from: date
    period_to: date
    basic_salary: float
    notes: str | None = None


class PayslipRead(_Base):
    id: int
    number: str
    employee_id: int
    structure_id: int
    state: str
    period_from: date
    period_to: date
    basic_salary: float
    total_allowances: float
    total_deductions: float
    net_salary: float
    sso_employee: float
    sso_employer: float
    provident_fund_employee: float
    provident_fund_employer: float
    income_tax: float
    net_after_tax: float
    lines: list[PayslipLineRead] = []

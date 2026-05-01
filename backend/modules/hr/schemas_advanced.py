"""Pydantic schemas for HR advanced (Phase 14)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── SSO ────────────────────────────────────────────────────────────────


SsoInsuredType = Literal["article33", "article39", "article40"]


class SsoRegistrationCreate(BaseModel):
    employee_id: int
    ssn: str = Field(min_length=1, max_length=20)
    registered_date: date
    branch_code: str | None = None
    insured_type: SsoInsuredType = "article33"


class SsoRegistrationRead(_ORM):
    id: int
    employee_id: int
    ssn: str
    registered_date: date
    branch_code: str | None
    insured_type: str
    active: bool


class SsoContributionCreate(BaseModel):
    company_id: int
    employee_id: int
    period_year: int = Field(ge=2000, le=2100)
    period_month: int = Field(ge=1, le=12)
    gross_wage: float = Field(gt=0)


class SsoContributionRead(_ORM):
    id: int
    company_id: int
    employee_id: int
    period_year: int
    period_month: int
    gross_wage: float
    employee_amount: float
    employer_amount: float
    paid_at: datetime | None


# ── PND filing ─────────────────────────────────────────────────────────


PndFilingType = Literal["pnd1", "pnd1a", "pnd2", "pnd3", "pnd53"]


class PndFilingCreate(BaseModel):
    company_id: int
    filing_type: PndFilingType = "pnd1"
    period_year: int = Field(ge=2000, le=2100)
    period_month: int = Field(ge=1, le=12)
    note: str | None = None


class PndFilingLineRead(_ORM):
    id: int
    filing_id: int
    employee_id: int
    employee_name: str
    national_id: str | None
    gross_wage: float
    deductions: float
    taxable_income: float
    wht_amount: float
    wht_rate_pct: float


class PndFilingRead(_ORM):
    id: int
    company_id: int
    filing_type: str
    state: str
    period_year: int
    period_month: int
    total_gross_wage: float
    total_wht: float
    submitted_at: datetime | None
    submitted_by: int | None
    rd_receipt_number: str | None
    note: str | None
    lines: list[PndFilingLineRead] = Field(default_factory=list)


# ── Overtime ───────────────────────────────────────────────────────────


OtKind = Literal[
    "weekday_after_hours", "weekend_normal", "weekend_after_hours", "holiday"
]


class OvertimeRecordCreate(BaseModel):
    company_id: int
    employee_id: int
    work_date: date
    ot_kind: OtKind
    hours: float = Field(gt=0)
    base_hourly_rate: float = Field(gt=0)
    note: str | None = None


class OvertimeRecordRead(_ORM):
    id: int
    company_id: int
    employee_id: int
    work_date: date
    ot_kind: str
    hours: float
    base_hourly_rate: float
    rate_multiplier: float
    total_amount: float
    state: str
    note: str | None


class OvertimeCalcRequest(BaseModel):
    ot_kind: OtKind
    hours: float = Field(gt=0)
    base_hourly_rate: float = Field(gt=0)


class OvertimeCalcResult(BaseModel):
    ot_kind: str
    hours: float
    base_hourly_rate: float
    rate_multiplier: float
    total_amount: float


# ── Leave entitlement ──────────────────────────────────────────────────


class LeaveEntitlementCreate(BaseModel):
    employee_id: int
    leave_type_id: int
    year: int = Field(ge=2000, le=2100)
    granted_days: float = Field(ge=0)
    carried_over: float = 0


class LeaveEntitlementRead(_ORM):
    id: int
    employee_id: int
    leave_type_id: int
    year: int
    granted_days: float
    carried_over: float
    used_days: float
    remaining_days: float


class LeaveAccrualRequest(BaseModel):
    employee_id: int
    year: int


class LeaveAccrualResult(BaseModel):
    employee_id: int
    year: int
    years_of_service: int
    granted_days: float
    rule_applied: str


# ── Employee transfer ──────────────────────────────────────────────────


class EmployeeTransferCreate(BaseModel):
    employee_id: int
    from_company_id: int
    to_company_id: int
    effective_date: date
    new_position: str | None = None
    new_department_id: int | None = None
    new_warehouse_id: int | None = None
    salary_adjustment_pct: float = 0
    keep_service_date: bool = True
    keep_leave_balance: bool = True
    reason: str | None = None


class EmployeeTransferRead(_ORM):
    id: int
    employee_id: int
    from_company_id: int
    to_company_id: int
    state: str
    effective_date: date
    new_position: str | None
    new_department_id: int | None
    new_warehouse_id: int | None
    salary_adjustment_pct: float
    keep_service_date: bool
    keep_leave_balance: bool
    completed_at: datetime | None
    reason: str | None

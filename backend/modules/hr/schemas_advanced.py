"""Pydantic schemas for advanced HR models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class JobPositionCreate(BaseModel):
    name: str
    department_id: int | None = None
    no_of_recruitment: int = 0
    active: bool = True


class JobPositionRead(JobPositionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ContractCreate(BaseModel):
    employee_id: int
    structure_id: int
    contract_type: str = "permanent"
    wage: float
    date_start: date
    date_end: date | None = None
    notes: str | None = None


class ContractRead(ContractCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    state: str
    created_at: datetime


class AppraisalLineCreate(BaseModel):
    criteria: str
    weight: float = 1.0
    score: float = 0
    comments: str | None = None


class AppraisalLineRead(AppraisalLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    appraisal_id: int


class AppraisalCreate(BaseModel):
    employee_id: int
    manager_id: int | None = None
    period: str
    lines: list[AppraisalLineCreate] = []


class AppraisalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    manager_id: int | None
    state: str
    period: str
    overall_score: float
    done_at: datetime | None
    created_at: datetime
    lines: list[AppraisalLineRead] = []


class ExpenseLineCreate(BaseModel):
    description: str
    amount: float
    account_id: int | None = None


class ExpenseLineRead(ExpenseLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    expense_id: int


class ExpenseCreate(BaseModel):
    employee_id: int
    name: str
    expense_date: date
    account_id: int | None = None
    lines: list[ExpenseLineCreate] = []


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    name: str
    state: str
    expense_date: date
    total_amount: float
    approved_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    lines: list[ExpenseLineRead] = []


class TrainingCourseCreate(BaseModel):
    name: str
    provider: str | None = None
    duration_hours: float = 8.0
    mandatory: bool = False
    active: bool = True


class TrainingCourseRead(TrainingCourseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class TrainingEnrollmentCreate(BaseModel):
    employee_id: int
    course_id: int
    enrolled_at: date
    completed_at: date | None = None
    status: str = "enrolled"


class TrainingEnrollmentRead(TrainingEnrollmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ProvidentFundCreate(BaseModel):
    name: str
    fund_code: str
    employee_rate_pct: float = 5.0
    employer_rate_pct: float = 5.0
    fund_manager: str | None = None
    active: bool = True


class ProvidentFundRead(ProvidentFundCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ThaiSsoResult(BaseModel):
    sso_base: float
    rate_pct: float
    sso_amount: float
    employer_amount: float


class ThaiTaxResult(BaseModel):
    annual_income: float
    net_income: float
    annual_tax: float
    monthly_tax: float


class PvdResult(BaseModel):
    contribution_employee: float
    contribution_employer: float


class Pnd1LineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    payslip_id: int
    period_month: int
    period_year: int
    taxable_income: float
    cumulative_income: float
    wht_amount: float
    wht_method: str


class Pnd1GeneratePayload(BaseModel):
    company_id: int
    period_month: int
    period_year: int


class ShiftRosterCreate(BaseModel):
    employee_id: int
    shift_id: int | None = None
    roster_date: date
    status: str = "scheduled"


class ShiftRosterRead(ShiftRosterCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class OvertimeRequestCreate(BaseModel):
    employee_id: int
    ot_date: date
    hours: float
    rate_multiplier: float = 1.5
    reason: str | None = None


class OvertimeRequestRead(OvertimeRequestCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    state: str
    approved_by_id: int | None
    approved_at: datetime | None
    created_at: datetime


class ApprovePayload(BaseModel):
    approver_id: int

"""Pydantic schemas for accounting advanced (Phase 14)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── VAT period ─────────────────────────────────────────────────────────


VatDirection = Literal["input", "output"]


class VatPeriodCreate(BaseModel):
    company_id: int
    period_year: int = Field(ge=2000, le=2100)
    period_month: int = Field(ge=1, le=12)
    note: str | None = None


class VatLineCreate(BaseModel):
    direction: VatDirection
    document_date: date
    counterparty_name: str
    counterparty_tax_id: str | None = None
    invoice_number: str | None = None
    base_amount: float = Field(gt=0)
    vat_amount: float = Field(ge=0)
    total_amount: float = Field(gt=0)
    source_model: str | None = None
    source_id: int | None = None


class VatLineRead(_ORM):
    id: int
    period_id: int
    direction: str
    document_date: date
    counterparty_name: str
    counterparty_tax_id: str | None
    invoice_number: str | None
    base_amount: float
    vat_amount: float
    total_amount: float


class VatPeriodRead(_ORM):
    id: int
    company_id: int
    state: str
    period_year: int
    period_month: int
    output_vat: float
    input_vat: float
    net_payable: float
    credit_carried_forward: float
    submitted_at: datetime | None
    submitted_by: int | None
    rd_receipt_number: str | None
    note: str | None
    lines: list[VatLineRead] = Field(default_factory=list)


# ── WHT certificate ────────────────────────────────────────────────────


WhtFormType = Literal["pnd1", "pnd1a", "pnd2", "pnd3", "pnd53"]


class WhtCertificateCreate(BaseModel):
    company_id: int
    form_type: WhtFormType
    period_year: int = Field(ge=2000, le=2100)
    period_month: int = Field(ge=1, le=12)
    issue_date: date
    payee_name: str = Field(min_length=1, max_length=255)
    payee_tax_id: str = Field(min_length=1, max_length=40)
    payee_address: str | None = None
    income_type_code: str
    income_description: str | None = None
    gross_amount: float = Field(gt=0)
    wht_rate_pct: float = Field(ge=0)
    journal_entry_id: int | None = None
    note: str | None = None


class WhtCertificateRead(_ORM):
    id: int
    company_id: int
    form_type: str
    sequence_number: int
    period_year: int
    period_month: int
    issue_date: date
    payee_name: str
    payee_tax_id: str
    payee_address: str | None
    income_type_code: str
    income_description: str | None
    gross_amount: float
    wht_rate_pct: float
    wht_amount: float
    journal_entry_id: int | None
    note: str | None


# ── Fixed asset + depreciation ─────────────────────────────────────────


DepreciationMethod = Literal["straight_line", "declining_balance", "units_of_production"]


class FixedAssetCreate(BaseModel):
    company_id: int
    asset_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = None
    acquisition_date: date
    acquisition_cost: float = Field(gt=0)
    salvage_value: float = 0
    depreciation_method: DepreciationMethod = "straight_line"
    useful_life_months: int = Field(gt=0)
    asset_account_id: int | None = None
    accumulated_depreciation_account_id: int | None = None
    depreciation_expense_account_id: int | None = None
    location: str | None = None
    custodian_employee_id: int | None = None
    note: str | None = None


class DepreciationEntryRead(_ORM):
    id: int
    asset_id: int
    period_year: int
    period_month: int
    depreciation_amount: float
    accumulated_to_date: float
    book_value_after: float
    posted_at: datetime | None
    journal_entry_id: int | None


class FixedAssetRead(_ORM):
    id: int
    company_id: int
    asset_code: str
    name: str
    category: str | None
    state: str
    acquisition_date: date
    acquisition_cost: float
    salvage_value: float
    depreciation_method: str
    useful_life_months: int
    accumulated_depreciation: float
    book_value: float
    asset_account_id: int | None
    location: str | None
    custodian_employee_id: int | None
    disposal_date: date | None
    disposal_proceeds: float | None
    note: str | None
    schedule: list[DepreciationEntryRead] = Field(default_factory=list)


class DepreciationGenerateRequest(BaseModel):
    asset_id: int


class DepreciationCalcResult(BaseModel):
    asset_id: int
    method: str
    monthly_amount: float
    total_periods: int
    total_depreciation: float


# ── FX revaluation ─────────────────────────────────────────────────────


class FxRevaluationCreate(BaseModel):
    company_id: int
    currency: str = Field(min_length=3, max_length=10)
    period_year: int = Field(ge=2000, le=2100)
    period_month: int = Field(ge=1, le=12)
    period_end_rate: float = Field(gt=0)
    booked_balance_fc: float
    booked_balance_thb: float
    journal_entry_id: int | None = None
    note: str | None = None


class FxRevaluationRead(_ORM):
    id: int
    company_id: int
    currency: str
    period_year: int
    period_month: int
    period_end_rate: float
    booked_balance_fc: float
    booked_balance_thb: float
    revalued_balance_thb: float
    fx_gain_loss: float
    posted_at: datetime | None
    journal_entry_id: int | None
    note: str | None

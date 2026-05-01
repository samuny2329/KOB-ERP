"""Pydantic schemas for the Phase 12 group extras."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Cross-company customer ─────────────────────────────────────────────


class CrossCompanyCustomerLinkCreate(BaseModel):
    company_id: int
    local_customer_id: int
    is_primary: bool = False


class CrossCompanyCustomerLinkRead(_ORM):
    id: int
    profile_id: int
    company_id: int
    local_customer_id: int
    joined_at: datetime
    is_primary: bool


class CrossCompanyCustomerCreate(BaseModel):
    group_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = None
    tax_id: str | None = None
    primary_email: str | None = None
    primary_phone: str | None = None
    customer_group: str = "regular"
    group_credit_limit: float = 0
    note: str | None = None
    links: list[CrossCompanyCustomerLinkCreate] = Field(default_factory=list)


class CrossCompanyCustomerRead(_ORM):
    id: int
    group_code: str
    name: str
    legal_name: str | None
    tax_id: str | None
    primary_email: str | None
    primary_phone: str | None
    customer_group: str
    group_credit_limit: float
    group_credit_consumed: float
    group_ltv_score: float
    blocked: bool
    blocked_reason: str | None
    note: str | None
    active: bool
    links: list[CrossCompanyCustomerLinkRead] = Field(default_factory=list)


# ── Cross-company vendor ───────────────────────────────────────────────


class CrossCompanyVendorLinkCreate(BaseModel):
    company_id: int
    local_vendor_id: int
    is_primary: bool = False


class CrossCompanyVendorLinkRead(_ORM):
    id: int
    profile_id: int
    company_id: int
    local_vendor_id: int
    joined_at: datetime
    is_primary: bool


class CrossCompanyVendorCreate(BaseModel):
    group_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = None
    tax_id: str | None = None
    payment_currency: str = "THB"
    links: list[CrossCompanyVendorLinkCreate] = Field(default_factory=list)


class CrossCompanyVendorRead(_ORM):
    id: int
    group_code: str
    name: str
    legal_name: str | None
    tax_id: str | None
    payment_currency: str
    lifetime_spend: float
    ytd_spend: float
    group_otd_pct: float
    group_quality_pct: float
    group_score: float
    blocked: bool
    blocked_reason: str | None
    active: bool
    links: list[CrossCompanyVendorLinkRead] = Field(default_factory=list)


# ── Volume rebate ──────────────────────────────────────────────────────


PeriodKind = Literal["monthly", "quarterly", "annual"]


class VolumeRebateTierCreate(BaseModel):
    vendor_profile_id: int
    period_kind: PeriodKind = "annual"
    min_spend: float = 0
    max_spend: float | None = None
    rebate_pct: float = Field(ge=0, le=100)
    note: str | None = None


class VolumeRebateTierRead(_ORM):
    id: int
    vendor_profile_id: int
    period_kind: str
    min_spend: float
    max_spend: float | None
    rebate_pct: float
    note: str | None
    active: bool


class VolumeRebateAccrualRead(_ORM):
    id: int
    vendor_profile_id: int
    period_kind: str
    period_start: date
    period_end: date
    total_group_spend: float
    matched_tier_pct: float
    accrued_rebate: float
    settled_amount: float
    settled_at: datetime | None
    note: str | None


class RebateAccrualCompute(BaseModel):
    vendor_profile_id: int
    period_kind: PeriodKind
    period_start: date
    period_end: date
    total_group_spend: float = Field(gt=0)


# ── Bank + cash pool ───────────────────────────────────────────────────


BankAccountType = Literal["checking", "savings", "fixed", "credit_line", "petty_cash"]


class BankAccountCreate(BaseModel):
    company_id: int
    bank_name: str = Field(min_length=1, max_length=120)
    branch: str | None = None
    account_number: str = Field(min_length=1, max_length=40)
    account_name: str = Field(min_length=1, max_length=255)
    account_type: BankAccountType = "checking"
    currency: str = "THB"
    current_balance: float = 0


class BankAccountRead(_ORM):
    id: int
    company_id: int
    bank_name: str
    branch: str | None
    account_number: str
    account_name: str
    account_type: str
    currency: str
    current_balance: float
    available_balance: float
    last_reconciled_at: datetime | None
    active: bool


class CashPoolMemberCreate(BaseModel):
    bank_account_id: int
    priority: int = 10
    min_balance: float = 0


class CashPoolMemberRead(_ORM):
    id: int
    pool_id: int
    bank_account_id: int
    priority: int
    min_balance: float


class CashPoolCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    parent_company_id: int
    target_balance: float = 0
    currency: str = "THB"
    sweep_threshold_pct: float = 20
    note: str | None = None
    members: list[CashPoolMemberCreate] = Field(default_factory=list)


class CashPoolRead(_ORM):
    id: int
    code: str
    name: str
    parent_company_id: int
    target_balance: float
    currency: str
    sweep_threshold_pct: float
    note: str | None
    active: bool
    members: list[CashPoolMemberRead] = Field(default_factory=list)


class CashForecastSnapshotCreate(BaseModel):
    company_id: int
    forecast_date: date
    horizon_days: int = 30
    currency: str = "THB"
    opening_balance: float = 0
    cash_in: float = 0
    cash_out: float = 0
    breakdown: dict | None = None


class CashForecastSnapshotRead(_ORM):
    id: int
    company_id: int
    forecast_date: date
    horizon_days: int
    currency: str
    opening_balance: float
    cash_in: float
    cash_out: float
    projected_balance: float
    risk_flag: str


class GroupAccrualCreate(BaseModel):
    ref: str
    description: str
    paying_company_id: int
    total_amount: float = Field(gt=0)
    currency: str = "THB"
    accrual_basis: PeriodKind = "monthly"
    period_start: date
    period_end: date
    note: str | None = None


class GroupAccrualRead(_ORM):
    id: int
    ref: str
    description: str
    paying_company_id: int
    total_amount: float
    currency: str
    accrual_basis: str
    period_start: date
    period_end: date
    accrued_to_date: float
    state: str
    note: str | None


# ── SKU bridge ─────────────────────────────────────────────────────────


class SkuBridgeMemberCreate(BaseModel):
    company_id: int
    local_product_id: int
    local_sku: str | None = None
    note: str | None = None


class SkuBridgeMemberRead(_ORM):
    id: int
    bridge_id: int
    company_id: int
    local_product_id: int
    local_sku: str | None
    note: str | None


class SkuBridgeCreate(BaseModel):
    master_sku: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = None
    barcode: str | None = None
    members: list[SkuBridgeMemberCreate] = Field(default_factory=list)


class SkuBridgeRead(_ORM):
    id: int
    master_sku: str
    name: str
    description: str | None
    category: str | None
    barcode: str | None
    active: bool
    members: list[SkuBridgeMemberRead] = Field(default_factory=list)


class SkuBridgeResolveRequest(BaseModel):
    company_id: int
    master_sku: str | None = None
    local_sku: str | None = None
    local_product_id: int | None = None


class SkuBridgeResolveResult(BaseModel):
    matched: bool
    bridge_id: int | None
    master_sku: str | None
    local_product_id: int | None
    local_sku: str | None


# ── Brand license ──────────────────────────────────────────────────────


LicenseScope = Literal["exclusive", "non_exclusive", "co_exclusive"]


class BrandLicenseCreate(BaseModel):
    brand_code: str = Field(min_length=1, max_length=40)
    brand_name: str = Field(min_length=1, max_length=120)
    owner_company_id: int
    licensed_to_company_id: int
    territory: str = "TH"
    license_scope: LicenseScope = "non_exclusive"
    royalty_pct: float = Field(ge=0, le=100, default=0)
    minimum_royalty_per_period: float = 0
    period_kind: PeriodKind = "quarterly"
    product_category_ids: dict | None = None
    valid_from: date
    valid_to: date | None = None
    note: str | None = None


class BrandLicenseRead(_ORM):
    id: int
    brand_code: str
    brand_name: str
    owner_company_id: int
    licensed_to_company_id: int
    territory: str
    license_scope: str
    royalty_pct: float
    minimum_royalty_per_period: float
    period_kind: str
    valid_from: date
    valid_to: date | None
    note: str | None
    active: bool


# ── Transfer pricing ───────────────────────────────────────────────────


PricingMethod = Literal["cost_plus", "fixed", "market", "resale_minus", "tnmm"]


class TransferPricingAgreementCreate(BaseModel):
    from_company_id: int
    to_company_id: int
    product_category_id: int | None = None
    method: PricingMethod = "cost_plus"
    markup_pct: float = 0
    fixed_price: float | None = None
    valid_from: date
    valid_to: date | None = None
    documentation_url: str | None = None
    note: str | None = None


class TransferPricingAgreementRead(_ORM):
    id: int
    from_company_id: int
    to_company_id: int
    product_category_id: int | None
    method: str
    markup_pct: float
    fixed_price: float | None
    valid_from: date
    valid_to: date | None
    documentation_url: str | None
    note: str | None
    active: bool


class TransferPricingLookup(BaseModel):
    from_company_id: int
    to_company_id: int
    product_category_id: int | None = None
    on_date: date | None = None


class TransferPricingResult(BaseModel):
    matched: bool
    agreement_id: int | None
    method: str | None
    markup_pct: float | None
    fixed_price: float | None


# ── Approval substitution ──────────────────────────────────────────────


class ApprovalSubstitutionCreate(BaseModel):
    primary_user_id: int
    fallback_user_id: int
    primary_company_id: int | None = None
    document_type: str | None = None
    valid_from: date
    valid_to: date
    reason: str | None = None


class ApprovalSubstitutionRead(_ORM):
    id: int
    primary_user_id: int
    fallback_user_id: int
    primary_company_id: int | None
    document_type: str | None
    valid_from: date
    valid_to: date
    reason: str | None
    active: bool


class ApproverResolveRequest(BaseModel):
    user_id: int
    on_date: date | None = None
    document_type: str | None = None


class ApproverResolveResult(BaseModel):
    primary_user_id: int
    effective_user_id: int
    substituted: bool
    substitution_id: int | None = None
    reason: str | None = None

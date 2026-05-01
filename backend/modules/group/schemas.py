"""Pydantic schemas for the group module."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


# ── Company ────────────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    code: str
    name: str
    tax_id: str | None = None
    country: str = "THA"
    currency: str = "THB"
    parent_id: int | None = None
    active: bool = True


class CompanyRead(CompanyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ── Company Group & Membership ─────────────────────────────────────────

class CompanyGroupCreate(BaseModel):
    name: str
    root_company_id: int | None = None
    consolidation_currency: str = "THB"
    active: bool = True


class CompanyGroupRead(CompanyGroupCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CompanyMembershipCreate(BaseModel):
    company_id: int
    group_id: int
    role: str = "subsidiary"
    ownership_pct: float = 0
    effective_from: date | None = None
    effective_to: date | None = None


class CompanyMembershipRead(CompanyMembershipCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── Group Customer/Vendor ──────────────────────────────────────────────

class GroupCustomerProfileCreate(BaseModel):
    group_code: str
    name: str
    group_credit_limit: float = 0
    group_ltv_score: float = 0
    blocked: bool = False
    blocked_reason: str | None = None


class GroupCustomerProfileRead(GroupCustomerProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class GroupCustomerLinkCreate(BaseModel):
    group_customer_id: int
    company_id: int
    customer_id: int


class GroupCustomerLinkRead(GroupCustomerLinkCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class GroupVendorProfileCreate(BaseModel):
    group_code: str
    name: str
    lifetime_spend: float = 0
    ytd_spend: float = 0
    group_otd_pct: float = 0
    group_quality_pct: float = 100
    group_score: float = 100


class GroupVendorProfileRead(GroupVendorProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class GroupVendorLinkCreate(BaseModel):
    group_vendor_id: int
    company_id: int
    vendor_id: int


class GroupVendorLinkRead(GroupVendorLinkCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── Rebate ─────────────────────────────────────────────────────────────

class VolumeRebateTierCreate(BaseModel):
    group_vendor_id: int
    tier_label: str
    min_spend: float
    rebate_pct: float
    period_type: str = "annual"


class VolumeRebateTierRead(VolumeRebateTierCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class VolumeRebateAccrualRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_vendor_id: int
    period: str
    accrued_amount: float
    tier_matched: str | None
    snapshot_at: datetime


class RebateComputePayload(BaseModel):
    group_vendor_id: int
    period: str
    ytd_spend: float


# ── SKU Bridge ─────────────────────────────────────────────────────────

class SkuBridgeItemCreate(BaseModel):
    company_id: int
    product_id: int
    local_sku: str | None = None


class SkuBridgeItemRead(SkuBridgeItemCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bridge_id: int


class CrossCompanySkuBridgeCreate(BaseModel):
    master_sku: str
    master_name: str
    active: bool = True
    items: list[SkuBridgeItemCreate] = []


class CrossCompanySkuBridgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    master_sku: str
    master_name: str
    active: bool
    created_at: datetime
    items: list[SkuBridgeItemRead] = []


class SkuResolvePayload(BaseModel):
    master_sku: str
    company_id: int


class SkuResolveResult(BaseModel):
    master_sku: str
    company_id: int
    product_id: int | None
    local_sku: str | None


# ── Finance ────────────────────────────────────────────────────────────

class BankAccountCreate(BaseModel):
    company_id: int
    bank_name: str
    account_no: str
    currency: str = "THB"
    account_type: str = "current"
    active: bool = True


class BankAccountRead(BankAccountCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CashPoolCreate(BaseModel):
    pool_name: str
    lead_company_id: int
    currency: str = "THB"
    target_balance: float = 0
    sweep_threshold: float = 0
    active: bool = True


class CashPoolRead(CashPoolCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CashForecastSnapshotCreate(BaseModel):
    company_id: int
    forecast_date: date
    opening: float
    projected_in: float
    projected_out: float
    closing: float
    risk_flag: str = "ok"


class CashForecastSnapshotRead(CashForecastSnapshotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class IntercompanyLoanCreate(BaseModel):
    lender_id: int
    borrower_id: int
    principal: float
    interest_rate: float
    term_months: int
    outstanding: float
    next_payment_date: date | None = None
    currency: str = "THB"


class IntercompanyLoanRead(IntercompanyLoanCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CostAllocationLineCreate(BaseModel):
    company_id: int
    share_pct: float
    amount: float
    basis_value: float = 0


class CostAllocationLineRead(CostAllocationLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    allocation_id: int


class CrossCompanyCostAllocationCreate(BaseModel):
    name: str
    total_amount: float
    basis: str
    period: str
    lines: list[CostAllocationLineCreate] = []


class CrossCompanyCostAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    state: str
    total_amount: float
    basis: str
    period: str
    validated_at: datetime | None
    created_at: datetime
    lines: list[CostAllocationLineRead] = []


class TransferPriceRuleCreate(BaseModel):
    from_company_id: int
    to_company_id: int
    product_category: str | None = None
    method: str = "cost_plus"
    markup_pct: float = 0
    documentation_url: str | None = None
    active: bool = True


class TransferPriceRuleRead(TransferPriceRuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class TransferPriceLookupPayload(BaseModel):
    from_company_id: int
    to_company_id: int
    product_category: str | None = None
    base_cost: float


class TransferPriceLookupResult(BaseModel):
    base_cost: float
    markup_pct: float
    transfer_price: float
    method: str
    rule_id: int | None


# ── Governance ─────────────────────────────────────────────────────────

class ComplianceCalendarCreate(BaseModel):
    company_id: int
    filing_type: str
    due_date: date
    period_month: int
    period_year: int


class ComplianceCalendarRead(ComplianceCalendarCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    state: str
    submitted_at: datetime | None
    ref_number: str | None
    created_at: datetime


class ComplianceSubmitPayload(BaseModel):
    ref_number: str | None = None


class CompanyApprovalMatrixCreate(BaseModel):
    company_id: int
    document_type: str
    amount_threshold: float
    approver_id: int
    min_approvers: int = 1


class CompanyApprovalMatrixRead(CompanyApprovalMatrixCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ApprovalSubstitutionCreate(BaseModel):
    company_id: int
    approver_id: int
    substitute_id: int
    document_type: str | None = None
    valid_from: date
    valid_to: date


class ApprovalSubstitutionRead(ApprovalSubstitutionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ResolveApproverPayload(BaseModel):
    company_id: int
    document_type: str
    amount: float


class ResolveApproverResult(BaseModel):
    approver_id: int
    is_substitute: bool


class BrandLicenseCreate(BaseModel):
    owner_company_id: int
    licensee_company_id: int
    brand_name: str
    territory: str | None = None
    royalty_pct: float
    license_scope: str = "non_exclusive"
    valid_from: date
    valid_to: date | None = None
    active: bool = True


class BrandLicenseRead(BrandLicenseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ── KPI ────────────────────────────────────────────────────────────────

class GroupKpiRollupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    period: str
    metric_name: str
    value: float
    computed_at: datetime


class KpiRollupComputePayload(BaseModel):
    group_id: int
    period: str
    metric_name: str


class InventoryPoolCreate(BaseModel):
    pool_name: str
    routing_strategy: str = "priority"
    active: bool = True
    description: str | None = None


class InventoryPoolRead(InventoryPoolCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime

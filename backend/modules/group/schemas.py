"""Pydantic schemas for the group / multi-company module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Group KPI ──────────────────────────────────────────────────────────


KpiMetric = Literal[
    "revenue", "gross_margin", "fulfillment_sla_pct", "pick_accuracy_pct",
    "ar_days", "ap_days", "headcount", "active_customers",
]


class GroupKpiSnapshotCreate(BaseModel):
    company_id: int
    metric: KpiMetric
    period_start: date
    period_end: date
    value: float
    unit: str | None = None
    breakdown: dict | None = None


class GroupKpiSnapshotRead(_ORM):
    id: int
    company_id: int
    metric: str
    period_start: date
    period_end: date
    value: float
    unit: str | None
    refreshed_at: datetime


class GroupKpiRollup(BaseModel):
    """Aggregated rollup result — sums children + the parent itself."""

    parent_company_id: int
    metric: str
    period_start: date
    period_end: date
    own_value: float
    children_value: float
    total_value: float
    children_breakdown: list[dict] = Field(default_factory=list)


# ── Inventory pool ─────────────────────────────────────────────────────


class InventoryPoolCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    parent_company_id: int
    note: str | None = None


class InventoryPoolRead(_ORM):
    id: int
    code: str
    name: str
    parent_company_id: int
    note: str | None
    active: bool


class InventoryPoolMemberCreate(BaseModel):
    company_id: int
    warehouse_id: int
    priority: int = 10
    transfer_cost_per_km: float = 0


class InventoryPoolMemberRead(_ORM):
    id: int
    pool_id: int
    company_id: int
    warehouse_id: int
    priority: int
    transfer_cost_per_km: float


RoutingStrategy = Literal["priority", "lowest_cost", "nearest", "balance_load"]


class InventoryPoolRuleCreate(BaseModel):
    sequence: int = 10
    product_category_id: int | None = None
    strategy: RoutingStrategy = "priority"
    min_qty_threshold: float = 0
    note: str | None = None


class InventoryPoolRuleRead(_ORM):
    id: int
    pool_id: int
    sequence: int
    product_category_id: int | None
    strategy: str
    min_qty_threshold: float
    note: str | None
    active: bool


class StockLookupRequest(BaseModel):
    product_id: int
    qty: float = Field(gt=0)


class StockLookupOption(BaseModel):
    company_id: int
    warehouse_id: int
    available_qty: float
    priority: int
    estimated_cost: float
    chosen: bool


# ── Cost allocation ────────────────────────────────────────────────────


AllocationBasis = Literal["revenue_pct", "headcount_pct", "fixed", "sqm_pct", "manual"]


class CostAllocationLineCreate(BaseModel):
    company_id: int
    share_pct: float = 0
    amount: float = 0
    note: str | None = None


class CostAllocationLineRead(_ORM):
    id: int
    allocation_id: int
    company_id: int
    share_pct: float
    amount: float
    note: str | None


class CostAllocationCreate(BaseModel):
    ref: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=255)
    paying_company_id: int
    period_start: date
    period_end: date
    total_amount: float = Field(gt=0)
    currency: str = "THB"
    basis: AllocationBasis
    expense_account_id: int | None = None
    note: str | None = None
    rules: list[CostAllocationLineCreate] = Field(default_factory=list)


class CostAllocationRead(_ORM):
    id: int
    ref: str
    description: str
    paying_company_id: int
    state: str
    period_start: date
    period_end: date
    total_amount: float
    currency: str
    basis: str
    expense_account_id: int | None
    posted_at: datetime | None
    note: str | None
    rules: list[CostAllocationLineRead] = Field(default_factory=list)


# ── Inter-company loan ─────────────────────────────────────────────────


class LoanInstallmentCreate(BaseModel):
    sequence: int
    due_date: date
    principal_due: float
    interest_due: float = 0


class LoanInstallmentRead(_ORM):
    id: int
    loan_id: int
    sequence: int
    due_date: date
    principal_due: float
    interest_due: float
    paid_amount: float
    paid_date: date | None
    state: str


class InterCompanyLoanCreate(BaseModel):
    ref: str = Field(min_length=1, max_length=40)
    lender_company_id: int
    borrower_company_id: int
    principal: float = Field(gt=0)
    interest_rate_pct: float = 0
    currency: str = "THB"
    issued_date: date
    due_date: date | None = None
    purpose: str | None = None
    installments: list[LoanInstallmentCreate] = Field(default_factory=list)


class InterCompanyLoanRead(_ORM):
    id: int
    ref: str
    state: str
    lender_company_id: int
    borrower_company_id: int
    principal: float
    interest_rate_pct: float
    currency: str
    issued_date: date
    due_date: date | None
    settled_date: date | None
    outstanding_balance: float
    purpose: str | None
    installments: list[LoanInstallmentRead] = Field(default_factory=list)


class LoanRepayment(BaseModel):
    installment_id: int
    paid_amount: float = Field(gt=0)
    paid_date: date


# ── Tax group ──────────────────────────────────────────────────────────


class TaxGroupMemberCreate(BaseModel):
    company_id: int
    joined_date: date


class TaxGroupMemberRead(_ORM):
    id: int
    tax_group_id: int
    company_id: int
    joined_date: date
    left_date: date | None


class TaxGroupCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=255)
    representative_company_id: int
    tax_authority_id: str | None = None
    effective_from: date
    effective_to: date | None = None
    members: list[TaxGroupMemberCreate] = Field(default_factory=list)


class TaxGroupRead(_ORM):
    id: int
    code: str
    name: str
    representative_company_id: int
    tax_authority_id: str | None
    effective_from: date
    effective_to: date | None
    active: bool
    members: list[TaxGroupMemberRead] = Field(default_factory=list)


# ── Approval matrix ────────────────────────────────────────────────────


ApprovableDoc = Literal[
    "purchase_order",
    "sales_order",
    "journal_entry",
    "leave",
    "payslip",
    "cost_allocation",
    "intercompany_loan",
]


class ApprovalMatrixRuleCreate(BaseModel):
    sequence: int = 10
    min_amount: float = 0
    max_amount: float | None = None
    approver_user_id: int | None = None
    approver_group_id: int | None = None
    requires_n_approvers: int = 1


class ApprovalMatrixRuleRead(_ORM):
    id: int
    matrix_id: int
    sequence: int
    min_amount: float
    max_amount: float | None
    approver_user_id: int | None
    approver_group_id: int | None
    requires_n_approvers: int
    active: bool


class ApprovalMatrixCreate(BaseModel):
    company_id: int
    document_type: ApprovableDoc
    note: str | None = None
    rules: list[ApprovalMatrixRuleCreate] = Field(default_factory=list)


class ApprovalMatrixRead(_ORM):
    id: int
    company_id: int
    document_type: str
    note: str | None
    active: bool
    rules: list[ApprovalMatrixRuleRead] = Field(default_factory=list)


class ApprovalLookupRequest(BaseModel):
    company_id: int
    document_type: ApprovableDoc
    amount: float


class ApprovalLookupResult(BaseModel):
    matched: bool
    rule_id: int | None
    approver_user_id: int | None
    approver_group_id: int | None
    requires_n_approvers: int


# ── Compliance ─────────────────────────────────────────────────────────


ComplianceType = Literal[
    "vat_pp30", "wht_pnd1", "wht_pnd3", "wht_pnd53", "social_security",
    "annual_audit", "corporate_pnd50", "half_year_pnd51",
    "trademark_renewal", "license_renewal", "other",
]


class ComplianceItemCreate(BaseModel):
    company_id: int
    compliance_type: ComplianceType
    period_label: str = Field(min_length=1, max_length=40)
    due_date: date
    note: str | None = None


class ComplianceItemRead(_ORM):
    id: int
    company_id: int
    compliance_type: str
    period_label: str
    state: str
    due_date: date
    submitted_date: date | None
    submitted_by: int | None
    reference_number: str | None
    amount_filed: float | None
    note: str | None

"""Pydantic schemas for advanced purchase models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Payment Terms ──────────────────────────────────────────────────────


class PaymentTermLineCreate(_Base):
    sequence: int = 0
    value_type: str = "percent"
    value: float = Field(default=100, gt=0)
    days: int = Field(default=30, ge=0)
    discount_pct: float = Field(default=0, ge=0, le=100)
    discount_days: int = Field(default=0, ge=0)


class PaymentTermLineRead(_Base):
    id: int
    sequence: int
    value_type: str
    value: float
    days: int
    discount_pct: float
    discount_days: int


class PaymentTermCreate(_Base):
    name: str = Field(min_length=1, max_length=120)
    note: str | None = None
    active: bool = True
    lines: list[PaymentTermLineCreate] = Field(default_factory=list)


class PaymentTermRead(_Base):
    id: int
    name: str
    note: str | None = None
    active: bool
    lines: list[PaymentTermLineRead] = Field(default_factory=list)


# ── Supplier Pricelist ─────────────────────────────────────────────────


class SupplierPricelistCreate(_Base):
    vendor_id: int
    product_id: int
    min_qty: float = Field(default=0, ge=0)
    price: float = Field(gt=0)
    currency: str = "THB"
    lead_time_days: int = Field(default=1, ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    active: bool = True


class SupplierPricelistRead(_Base):
    id: int
    vendor_id: int
    product_id: int
    min_qty: float
    price: float
    currency: str
    lead_time_days: int
    effective_from: date | None = None
    effective_to: date | None = None
    active: bool


# ── Vendor Document Registry ───────────────────────────────────────────


class VendorDocumentCreate(_Base):
    vendor_id: int
    doc_type: str = Field(max_length=30)
    title: str = Field(min_length=1, max_length=240)
    reference: str | None = Field(default=None, max_length=80)
    issued_date: date | None = None
    expiry_date: date | None = None
    alert_days_before: int = Field(default=30, ge=0)
    file_url: str | None = Field(default=None, max_length=500)
    note: str | None = None
    active: bool = True


class VendorDocumentRead(_Base):
    id: int
    vendor_id: int
    doc_type: str
    title: str
    reference: str | None = None
    issued_date: date | None = None
    expiry_date: date | None = None
    alert_days_before: int
    file_url: str | None = None
    active: bool


# ── Vendor Performance ─────────────────────────────────────────────────


class VendorPerformanceRead(_Base):
    id: int
    vendor_id: int
    period_year: int
    period_month: int
    on_time_rate: float
    fill_rate: float
    quality_rate: float
    price_stability: float
    overall_score: float
    po_count: int
    receipt_count: int
    computed_at: datetime


# ── Thai WHT Certificate ───────────────────────────────────────────────


class WhtCertificateCreate(_Base):
    purchase_order_id: int
    vendor_id: int
    certificate_no: str | None = None
    wht_type: str = "pnd53"
    wht_rate: float = Field(default=3.0, gt=0, le=100)
    base_amount: float = Field(gt=0)
    wht_amount: float = Field(gt=0)
    payment_date: date
    period_month: int = Field(ge=1, le=12)
    period_year: int


class WhtCertificateRead(_Base):
    id: int
    purchase_order_id: int
    vendor_id: int
    certificate_no: str | None = None
    wht_type: str
    wht_rate: float
    base_amount: float
    wht_amount: float
    payment_date: date
    period_month: int
    period_year: int
    submitted: bool
    submitted_at: datetime | None = None


# ── Procurement Budget ─────────────────────────────────────────────────


class ProcurementBudgetCreate(_Base):
    name: str = Field(min_length=1, max_length=120)
    department: str | None = None
    project_code: str | None = None
    fiscal_year: int
    period_from: date
    period_to: date
    currency: str = "THB"
    total_budget: float = Field(gt=0)
    auto_block_overrun: bool = True
    owner_id: int | None = None


class ProcurementBudgetRead(_Base):
    id: int
    name: str
    department: str | None = None
    project_code: str | None = None
    fiscal_year: int
    period_from: date
    period_to: date
    currency: str
    total_budget: float
    committed_amount: float
    spent_amount: float
    state: str
    auto_block_overrun: bool

    @property
    def remaining(self) -> float:
        return float(self.total_budget) - float(self.committed_amount)

    @property
    def utilisation_pct(self) -> float:
        if float(self.total_budget) == 0:
            return 0.0
        return round(float(self.committed_amount) / float(self.total_budget) * 100, 1)


# ── Demand Signal ──────────────────────────────────────────────────────


class DemandSignalRead(_Base):
    id: int
    product_id: int
    vendor_id: int | None = None
    platform: str | None = None
    avg_daily_sales: float
    lead_time_days: int
    safety_stock: float
    current_on_hand: float
    suggested_qty: float
    suggested_price: float | None = None
    computed_at: datetime
    status: str
    converted_po_id: int | None = None


# ── PO Consolidation Proposal ──────────────────────────────────────────


class PoConsolidationItemRead(_Base):
    id: int
    purchase_order_id: int


class PoConsolidationProposalRead(_Base):
    id: int
    vendor_id: int
    status: str
    total_lines: int
    original_total: float
    estimated_saving: float
    saving_pct: float
    window_days: int
    proposed_at: datetime
    reviewed_at: datetime | None = None
    items: list[PoConsolidationItemRead] = Field(default_factory=list)


# ── PO Approval ────────────────────────────────────────────────────────


class PoApproveBody(_Base):
    note: str | None = None


class PoRejectBody(_Base):
    reason: str = Field(min_length=1)

"""Advanced purchase models — Odoo 19 parity + KOB-exclusive features.

Covers:
  - PaymentTerm          : flexible net/installment payment schedules
  - SupplierPricelist    : vendor-specific pricing with qty breaks
  - VendorDocument       : certifications, contracts, insurance with expiry alerts
  - VendorPerformance    : auto-computed KPI score per vendor
  - WhtCertificate       : Thai withholding tax (PND3 / PND53) per PO
  - ProcurementBudget    : department/project spend cap with real-time tracking
  - PurchaseBill         : PO ↔ vendor invoice link (3-way match)
  - DemandSignal         : platform sales velocity → purchase suggestion
  - PoConsolidationProposal : multi-PO consolidation engine suggestion
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


# ── Payment Terms ──────────────────────────────────────────────────────


class PaymentTerm(BaseModel):
    """Flexible payment schedule template.

    Examples: "Net 30", "2/10 Net 30" (2% discount if paid in 10 days),
    "50% advance + 50% on delivery".
    """

    __tablename__ = "payment_term"
    __table_args__ = ({"schema": "purchase"},)

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    lines: Mapped[list["PaymentTermLine"]] = relationship(
        back_populates="payment_term", cascade="all, delete-orphan", lazy="select"
    )


class PaymentTermLine(BaseModel):
    """One installment / tranche within a payment term.

    ``value_type`` ∈ {percent, balance}.  ``days`` = days after invoice date.
    ``discount_pct`` = early-payment discount if paid within ``discount_days``.
    """

    __tablename__ = "payment_term_line"
    __table_args__ = ({"schema": "purchase"},)

    payment_term_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.payment_term.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    value_type: Mapped[str] = mapped_column(String(10), default="percent")  # percent | balance
    value: Mapped[float] = mapped_column(Numeric(6, 4), default=100)  # e.g. 50.0 for 50%
    days: Mapped[int] = mapped_column(Integer, default=30)
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # early pay discount
    discount_days: Mapped[int] = mapped_column(Integer, default=0)

    payment_term: Mapped[PaymentTerm] = relationship(back_populates="lines", lazy="select")


# ── Supplier Pricelist ─────────────────────────────────────────────────


class SupplierPricelist(BaseModel):
    """Vendor-specific pricing with minimum quantity breaks.

    Odoo 19 equivalent: product.supplierinfo.
    KOB extension: effective_from / effective_to date range.
    """

    __tablename__ = "supplier_pricelist"
    __table_args__ = ({"schema": "purchase"},)

    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    min_qty: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB")
    lead_time_days: Mapped[int] = mapped_column(Integer, default=1)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Vendor Document Registry (KOB-exclusive) ──────────────────────────


VENDOR_DOC_TYPES = (
    "iso_cert",
    "food_safety",
    "factory_audit",
    "insurance",
    "contract",
    "tax_cert",
    "other",
)


class VendorDocument(BaseModel):
    """Vendor certification, insurance, or contract with expiry tracking.

    KOB-exclusive: no equivalent in Odoo 19 or SAP standard.
    Alerts are generated when expiry_date < today + alert_days_before.
    """

    __tablename__ = "vendor_document"
    __table_args__ = ({"schema": "purchase"},)

    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(80))  # cert number / contract ref
    issued_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    alert_days_before: Mapped[int] = mapped_column(Integer, default=30)
    file_url: Mapped[str | None] = mapped_column(String(500))  # S3 / object storage URL
    note: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Vendor Performance Score (KOB-exclusive) ──────────────────────────


class VendorPerformance(BaseModel):
    """Auto-computed KPI snapshot per vendor per month.

    KOB-exclusive: recomputed on every Receipt validation.
    Odoo has only manual star ratings.

    Scores are 0–100:
      - on_time_rate    : % of receipts validated on or before expected_date
      - fill_rate       : qty_accepted / qty_ordered (rolling 3 months)
      - quality_rate    : qty_accepted / qty_received (rolling 3 months)
      - price_stability : 1 - (std_dev(unit_price) / avg(unit_price)) — 100 = perfectly stable
      - overall_score   : weighted average (weights stored in config)
    """

    __tablename__ = "vendor_performance"
    __table_args__ = (
        UniqueConstraint("vendor_id", "period_year", "period_month", name="uq_vendor_perf_period"),
        {"schema": "purchase"},
    )

    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    on_time_rate: Mapped[float] = mapped_column(Float, default=0)       # 0-100
    fill_rate: Mapped[float] = mapped_column(Float, default=0)          # 0-100
    quality_rate: Mapped[float] = mapped_column(Float, default=0)       # 0-100
    price_stability: Mapped[float] = mapped_column(Float, default=0)    # 0-100
    overall_score: Mapped[float] = mapped_column(Float, default=0)      # 0-100
    po_count: Mapped[int] = mapped_column(Integer, default=0)
    receipt_count: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ── Thai WHT Registry (KOB-exclusive) ─────────────────────────────────


WHT_TYPES = ("pnd3", "pnd53")  # PND3 = individual, PND53 = juristic person
WHT_RATES = (1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 15.0)


class WhtCertificate(BaseModel):
    """Thai Withholding Tax certificate linked to a purchase order.

    KOB-exclusive: auto-calculated from PO total; generates PND3/PND53 data.
    Not available in any Western ERP without Thai localization add-on.
    """

    __tablename__ = "wht_certificate"
    __table_args__ = ({"schema": "purchase"},)

    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase.purchase_order.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="RESTRICT"), nullable=False
    )
    certificate_no: Mapped[str | None] = mapped_column(String(40), unique=True)
    wht_type: Mapped[str] = mapped_column(String(10), nullable=False, default="pnd53")
    wht_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=3.0)
    base_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    wht_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–12
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ── Procurement Budget Control (KOB-exclusive) ────────────────────────


BUDGET_STATES = ("draft", "active", "closed", "cancelled")


class ProcurementBudget(BaseModel, WorkflowMixin):
    """Department / project spend cap with real-time utilisation tracking.

    KOB-exclusive: integrated directly into PO approval flow.
    POs exceeding remaining budget are auto-held for manager approval.
    """

    __tablename__ = "procurement_budget"
    __table_args__ = ({"schema": "purchase"},)

    allowed_transitions = {
        "draft": {"active", "cancelled"},
        "active": {"closed", "cancelled"},
        "closed": set(),
        "cancelled": set(),
    }

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str | None] = mapped_column(String(80))
    project_code: Mapped[str | None] = mapped_column(String(40), index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB")
    total_budget: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    committed_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)  # confirmed POs
    spent_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)      # received POs
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    owner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL")
    )
    auto_block_overrun: Mapped[bool] = mapped_column(Boolean, default=True)


# ── PO ↔ Vendor Bill Link (Odoo 19 parity) ────────────────────────────


class PurchaseBill(BaseModel):
    """Links a PO to a vendor invoice in the accounting module.

    Enables 3-way matching: PO ↔ Receipt ↔ Bill.
    """

    __tablename__ = "purchase_bill"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "journal_entry_id", name="uq_po_bill"),
        {"schema": "purchase"},
    )

    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase.purchase_order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    journal_entry_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounting.journal_entry.id", ondelete="CASCADE"),
        nullable=False,
    )
    bill_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    matched: Mapped[bool] = mapped_column(Boolean, default=False)  # 3-way match confirmed


# ── Demand Signal → Purchase Suggestion (KOB-exclusive) ───────────────


class DemandSignal(BaseModel):
    """Platform sales velocity converted into a purchase suggestion.

    KOB-exclusive: reads from ops.platform_order data to project demand.
    Odoo has no native e-commerce demand → procurement integration.

    ``suggested_qty`` = (avg_daily_sales × lead_time_days) + safety_stock
                       - current_on_hand
    If > 0 → a purchase suggestion is raised for the buyer to review.
    """

    __tablename__ = "demand_signal"
    __table_args__ = ({"schema": "purchase"},)

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="SET NULL"), nullable=True
    )
    platform: Mapped[str | None] = mapped_column(String(30))  # shopee | lazada | tiktok | all
    avg_daily_sales: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    safety_stock: Mapped[float] = mapped_column(Float, default=0)
    current_on_hand: Mapped[float] = mapped_column(Float, default=0)
    suggested_qty: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_price: Mapped[float | None] = mapped_column(Numeric(14, 4))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | converted | ignored
    converted_po_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase.purchase_order.id", ondelete="SET NULL"), nullable=True
    )


# ── PO Consolidation Engine (KOB-exclusive) ───────────────────────────


class PoConsolidationProposal(BaseModel):
    """Suggested merge of multiple POs to the same vendor.

    KOB-exclusive: generated when reorder rules / demand signals
    produce ≥2 draft POs to the same vendor within a configurable window.
    Tracks estimated saving from volume discount.
    """

    __tablename__ = "po_consolidation_proposal"
    __table_args__ = ({"schema": "purchase"},)

    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | accepted | rejected
    total_lines: Mapped[int] = mapped_column(Integer, default=0)
    original_total: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    estimated_saving: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    saving_pct: Mapped[float] = mapped_column(Float, default=0)
    window_days: Mapped[int] = mapped_column(Integer, default=7)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL")
    )

    items: Mapped[list["PoConsolidationItem"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan", lazy="select"
    )


class PoConsolidationItem(BaseModel):
    """One PO included in a consolidation proposal."""

    __tablename__ = "po_consolidation_item"
    __table_args__ = ({"schema": "purchase"},)

    proposal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase.po_consolidation_proposal.id", ondelete="CASCADE"),
        nullable=False,
    )
    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase.purchase_order.id", ondelete="CASCADE"),
        nullable=False,
    )

    proposal: Mapped[PoConsolidationProposal] = relationship(back_populates="items", lazy="select")

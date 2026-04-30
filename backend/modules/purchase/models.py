"""Purchase models — vendors, POs, receipts, 3-way match."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


class Vendor(BaseModel):
    """Supplier / vendor master."""

    __tablename__ = "vendor"
    __table_args__ = ({"schema": "purchase"},)

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(30))
    contact_name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    payment_term_days: Mapped[int] = mapped_column(Integer, default=30)
    payment_term_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase.payment_term.id", ondelete="SET NULL"), nullable=True
    )
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    wht_type: Mapped[str] = mapped_column(String(10), default="pnd53", nullable=False)
    wht_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=3.0, nullable=False)
    performance_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="vendor", lazy="select")


PO_STATES = ["draft", "sent", "waiting_approval", "confirmed", "received", "closed", "cancelled"]

# Approval states (used when budget control or amount threshold requires approval)
PO_APPROVAL_STATES = ["not_required", "pending", "approved", "rejected"]

# Incoterms (Odoo 19 parity)
INCOTERMS = ("EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF")


class PurchaseOrder(BaseModel, WorkflowMixin):
    """Purchase order header."""

    __tablename__ = "purchase_order"
    __table_args__ = ({"schema": "purchase"},)

    allowed_transitions = {
        "draft": {"sent", "confirmed", "waiting_approval", "cancelled"},
        "sent": {"confirmed", "waiting_approval", "cancelled"},
        "waiting_approval": {"confirmed", "cancelled"},
        "confirmed": {"received", "closed", "cancelled"},
        "received": {"closed"},
        "closed": set(),
        "cancelled": set(),
    }

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL")
    )
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(10), default="THB")
    subtotal: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Odoo 19 parity additions
    note_internal: Mapped[str | None] = mapped_column(Text)
    note_vendor: Mapped[str | None] = mapped_column(Text)
    incoterms: Mapped[str | None] = mapped_column(String(10))
    buyer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    payment_term_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase.payment_term.id", ondelete="SET NULL"), nullable=True
    )
    # KOB-exclusive: approval + budget
    approval_state: Mapped[str] = mapped_column(String(20), default="not_required", nullable=False)
    approver_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    budget_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("purchase.procurement_budget.id", ondelete="SET NULL"),
        nullable=True,
    )

    vendor: Mapped[Vendor] = relationship(back_populates="orders", lazy="select")
    lines: Mapped[list["PoLine"]] = relationship(
        back_populates="order", lazy="select", cascade="all, delete-orphan"
    )


class PoLine(BaseModel):
    """Line item on a purchase order."""

    __tablename__ = "po_line"
    __table_args__ = ({"schema": "purchase"},)

    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.purchase_order.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(240))
    qty_ordered: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    qty_received: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    uom_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("wms.uom.id"))
    subtotal: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    # Odoo 19 parity: per-line tax
    tax_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.tax_rate.id", ondelete="SET NULL"), nullable=True
    )
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)   # e.g. 7.0 for 7% VAT
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(16, 2), default=0)     # subtotal + tax_amount

    order: Mapped[PurchaseOrder] = relationship(back_populates="lines", lazy="select")


class Receipt(BaseModel, WorkflowMixin):
    """Goods receipt against a PO — validated = quants updated."""

    __tablename__ = "receipt"
    __table_args__ = ({"schema": "purchase"},)

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.purchase_order.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="SET NULL")
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["ReceiptLine"]] = relationship(
        back_populates="receipt", lazy="select", cascade="all, delete-orphan"
    )


class ReceiptLine(BaseModel):
    """Individual line received on a receipt."""

    __tablename__ = "receipt_line"
    __table_args__ = ({"schema": "purchase"},)

    receipt_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.receipt.id", ondelete="CASCADE"), nullable=False
    )
    po_line_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase.po_line.id", ondelete="SET NULL")
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("wms.lot.id"))
    qty_received: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    qty_accepted: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    qty_rejected: Mapped[float] = mapped_column(Numeric(14, 4), default=0)

    receipt: Mapped[Receipt] = relationship(back_populates="lines", lazy="select")

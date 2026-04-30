"""Pydantic schemas for the purchase module."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VendorCreate(_Base):
    code: str
    name: str
    tax_id: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    payment_term_days: int = 30
    payment_term_id: int | None = None
    lead_time_days: int = 7
    wht_type: str = "pnd53"
    wht_rate: float = 3.0


class VendorRead(_Base):
    id: int
    code: str
    name: str
    tax_id: str | None
    contact_name: str | None
    email: str | None
    phone: str | None
    payment_term_days: int
    payment_term_id: int | None = None
    lead_time_days: int
    wht_type: str
    wht_rate: float
    performance_score: float
    active: bool


class PoLineCreate(_Base):
    product_id: int
    description: str | None = None
    qty_ordered: float
    unit_price: float
    uom_id: int | None = None
    tax_id: int | None = None
    tax_rate: float = 0.0


class PoLineRead(_Base):
    id: int
    product_id: int
    description: str | None
    qty_ordered: float
    qty_received: float
    unit_price: float
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float


class PurchaseOrderCreate(_Base):
    number: str
    vendor_id: int
    warehouse_id: int | None = None
    order_date: date
    expected_date: date | None = None
    currency: str = "THB"
    notes: str | None = None
    note_internal: str | None = None
    note_vendor: str | None = None
    incoterms: str | None = None
    buyer_id: int | None = None
    payment_term_id: int | None = None
    budget_id: int | None = None
    lines: list[PoLineCreate] = []


class PurchaseOrderRead(_Base):
    id: int
    number: str
    vendor_id: int
    state: str
    order_date: date
    expected_date: date | None
    currency: str
    subtotal: float
    tax_amount: float
    total_amount: float
    note_internal: str | None = None
    note_vendor: str | None = None
    incoterms: str | None = None
    buyer_id: int | None = None
    payment_term_id: int | None = None
    approval_state: str
    approved_at: datetime | None = None
    budget_id: int | None = None
    lines: list[PoLineRead] = []


class ReceiptLineCreate(_Base):
    product_id: int
    po_line_id: int | None = None
    lot_id: int | None = None
    qty_received: float
    qty_accepted: float = 0
    qty_rejected: float = 0


class ReceiptCreate(_Base):
    number: str
    purchase_order_id: int
    received_date: date
    location_id: int | None = None
    notes: str | None = None
    lines: list[ReceiptLineCreate] = []


class ReceiptLineRead(_Base):
    id: int
    product_id: int
    qty_received: float
    qty_accepted: float
    qty_rejected: float


class ReceiptRead(_Base):
    id: int
    number: str
    purchase_order_id: int
    state: str
    received_date: date
    lines: list[ReceiptLineRead] = []

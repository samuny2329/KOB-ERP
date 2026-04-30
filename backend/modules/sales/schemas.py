"""Pydantic schemas for the sales module."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerCreate(_Base):
    code: str
    name: str
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    credit_limit: float = 0
    payment_term_days: int = 30


class CustomerRead(_Base):
    id: int
    code: str
    name: str
    email: str | None
    phone: str | None
    credit_limit: float
    payment_term_days: int
    active: bool


class SoLineCreate(_Base):
    product_id: int
    description: str | None = None
    qty_ordered: float
    unit_price: float
    discount_pct: float = 0
    uom_id: int | None = None


class SoLineRead(_Base):
    id: int
    product_id: int
    qty_ordered: float
    qty_delivered: float
    unit_price: float
    discount_pct: float
    subtotal: float


class SalesOrderCreate(_Base):
    number: str
    customer_id: int
    order_date: date
    requested_date: date | None = None
    currency: str = "THB"
    shipping_address: str | None = None
    notes: str | None = None
    warehouse_id: int | None = None
    lines: list[SoLineCreate] = []


class SalesOrderRead(_Base):
    id: int
    number: str
    customer_id: int
    state: str
    order_date: date
    currency: str
    subtotal: float
    discount_amount: float
    tax_amount: float
    total_amount: float
    lines: list[SoLineRead] = []


class DeliveryLineCreate(_Base):
    product_id: int
    so_line_id: int | None = None
    qty_done: float
    lot_id: int | None = None


class DeliveryCreate(_Base):
    number: str
    sales_order_id: int
    scheduled_date: date | None = None
    carrier: str | None = None
    notes: str | None = None
    lines: list[DeliveryLineCreate] = []


class DeliveryLineRead(_Base):
    id: int
    product_id: int
    qty_done: float


class DeliveryRead(_Base):
    id: int
    number: str
    sales_order_id: int
    state: str
    scheduled_date: date | None
    carrier: str | None
    tracking_number: str | None
    lines: list[DeliveryLineRead] = []

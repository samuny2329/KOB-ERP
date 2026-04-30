"""Pydantic schemas for the outbound module API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Rack / Pickface / Courier (master data — wms schema) ──────────────


class RackCreate(BaseModel):
    zone_id: int
    location_id: int | None = None
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    capacity: float = 0
    frozen: bool = False


class RackRead(_ORM):
    id: int
    zone_id: int
    location_id: int | None = None
    code: str
    name: str
    capacity: float
    frozen: bool
    active: bool


class PickfaceCreate(BaseModel):
    zone_id: int
    location_id: int
    product_id: int
    code: str = Field(min_length=1, max_length=20)
    min_qty: float = 0
    max_qty: float = 0


class PickfaceRead(_ORM):
    id: int
    zone_id: int
    location_id: int
    product_id: int
    code: str
    min_qty: float
    max_qty: float
    active: bool


class CourierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    sequence: int = 10
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    tracking_url_template: str | None = None


class CourierRead(_ORM):
    id: int
    code: str
    name: str
    sequence: int
    color_hex: str | None = None
    tracking_url_template: str | None = None
    active: bool


# ── Outbound Order ─────────────────────────────────────────────────────


OrderState = Literal["pending", "picking", "picked", "packing", "packed", "shipped", "cancelled"]
PlatformLiteral = Literal["manual", "odoo", "shopee", "lazada", "tiktok", "pos"]


class OrderLineCreate(BaseModel):
    product_id: int
    qty_expected: float = Field(gt=0)
    lot_id: int | None = None
    sku: str | None = None
    description: str | None = None


class OrderLineRead(_ORM):
    id: int
    order_id: int
    product_id: int
    lot_id: int | None = None
    qty_expected: float
    qty_picked: float
    qty_packed: float
    sku: str | None = None
    description: str | None = None


class OrderCreate(BaseModel):
    ref: str = Field(min_length=1, max_length=40)
    customer_name: str = Field(min_length=1, max_length=255)
    platform: PlatformLiteral = "manual"
    courier_id: int | None = None
    note: str | None = None
    lines: list[OrderLineCreate] = Field(default_factory=list)


class OrderRead(_ORM):
    id: int
    ref: str
    customer_name: str
    platform: str
    state: str
    courier_id: int | None = None
    awb: str | None = None
    box_barcode: str | None = None
    note: str | None = None
    sla_start_at: datetime | None = None
    pick_start_at: datetime | None = None
    picked_at: datetime | None = None
    pack_start_at: datetime | None = None
    packed_at: datetime | None = None
    shipped_at: datetime | None = None
    picker_id: int | None = None
    packer_id: int | None = None
    shipper_id: int | None = None
    lines: list[OrderLineRead] = Field(default_factory=list)
    created_at: datetime


# ── DispatchBatch ──────────────────────────────────────────────────────


class DispatchBatchCreate(BaseModel):
    courier_id: int
    work_date: datetime | None = None
    note: str | None = None


class ScanItemRead(_ORM):
    id: int
    batch_id: int
    order_id: int | None = None
    barcode: str
    scanned_at: datetime
    scanned_by: int | None = None


class ScanItemCreate(BaseModel):
    barcode: str = Field(min_length=1, max_length=80)
    order_id: int | None = None


class DispatchBatchRead(_ORM):
    id: int
    name: str
    state: str
    courier_id: int
    work_date: datetime | None = None
    receiver_name: str | None = None
    dispatched_at: datetime | None = None
    dispatched_by: int | None = None
    note: str | None = None
    scans: list[ScanItemRead] = Field(default_factory=list)
    created_at: datetime


# ── Activity log ───────────────────────────────────────────────────────


class ActivityLogRead(_ORM):
    id: int
    actor_id: int | None = None
    action: str
    ref: str | None = None
    code: str | None = None
    note: str | None = None
    occurred_at: datetime
    prev_hash: str | None = None
    block_hash: str

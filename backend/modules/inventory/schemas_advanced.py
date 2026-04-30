"""Pydantic schemas for advanced inventory models (Odoo 19 parity features)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Package Type ───────────────────────────────────────────────────────


class PackageTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    width_cm: float | None = None
    length_cm: float | None = None
    height_cm: float | None = None
    max_weight_kg: float | None = None
    barcode: str | None = Field(default=None, max_length=60)
    active: bool = True


class PackageTypeRead(_ORM):
    id: int
    name: str
    width_cm: float | None = None
    length_cm: float | None = None
    height_cm: float | None = None
    max_weight_kg: float | None = None
    barcode: str | None = None
    active: bool


# ── Package ────────────────────────────────────────────────────────────


class PackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    package_type_id: int | None = None
    location_id: int | None = None
    parent_id: int | None = None
    owner_id: int | None = None
    weight_kg: float = 0.0


class PackageRead(_ORM):
    id: int
    name: str
    package_type_id: int | None = None
    location_id: int | None = None
    parent_id: int | None = None
    owner_id: int | None = None
    weight_kg: float


# ── Putaway Rules ──────────────────────────────────────────────────────


class PutawayRuleCreate(BaseModel):
    location_id: int
    location_dest_id: int
    product_id: int | None = None
    product_category_id: int | None = None
    package_type_id: int | None = None
    sequence: int = 0
    capacity_count: int | None = None
    active: bool = True


class PutawayRuleRead(_ORM):
    id: int
    location_id: int
    location_dest_id: int
    product_id: int | None = None
    product_category_id: int | None = None
    package_type_id: int | None = None
    sequence: int
    capacity_count: int | None = None
    active: bool


# ── Reorder Rules ──────────────────────────────────────────────────────


class ReorderRuleCreate(BaseModel):
    product_id: int
    location_id: int
    warehouse_id: int
    qty_min: float = Field(ge=0, default=0)
    qty_max: float = Field(ge=0, default=0)
    qty_multiple: float = Field(gt=0, default=1)
    lead_days: int = Field(ge=0, default=1)
    active: bool = True


class ReorderRuleUpdate(BaseModel):
    qty_min: float | None = Field(default=None, ge=0)
    qty_max: float | None = Field(default=None, ge=0)
    qty_multiple: float | None = Field(default=None, gt=0)
    lead_days: int | None = Field(default=None, ge=0)
    active: bool | None = None


class ReorderRuleRead(_ORM):
    id: int
    product_id: int
    location_id: int
    warehouse_id: int
    qty_min: float
    qty_max: float
    qty_multiple: float
    lead_days: int
    active: bool
    last_triggered_at: datetime | None = None
    last_qty_ordered: float | None = None


# ── Stock Valuation Layer ──────────────────────────────────────────────


class StockValuationLayerRead(_ORM):
    id: int
    product_id: int
    transfer_id: int | None = None
    transfer_line_id: int | None = None
    quantity: float
    unit_cost: float
    value: float
    remaining_qty: float
    remaining_value: float
    description: str | None = None
    landed_cost_id: int | None = None
    created_at: datetime


# ── Scrap Orders ───────────────────────────────────────────────────────


class ScrapOrderCreate(BaseModel):
    product_id: int
    lot_id: int | None = None
    package_id: int | None = None
    uom_id: int
    scrap_qty: float = Field(gt=0)
    source_location_id: int
    scrap_location_id: int
    origin: str | None = Field(default=None, max_length=120)
    scrap_reason: str | None = None
    unit_cost: float = 0.0


class ScrapOrderRead(_ORM):
    id: int
    name: str
    product_id: int
    lot_id: int | None = None
    package_id: int | None = None
    uom_id: int
    scrap_qty: float
    source_location_id: int
    scrap_location_id: int
    state: str
    origin: str | None = None
    scrap_reason: str | None = None
    done_at: datetime | None = None
    unit_cost: float
    total_cost: float
    created_at: datetime


# ── Landed Cost ────────────────────────────────────────────────────────


class LandedCostLineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)
    split_method: str = Field(default="by_quantity", max_length=20)
    account_id: int | None = None


class LandedCostLineRead(_ORM):
    id: int
    landed_cost_id: int
    name: str
    amount: float
    split_method: str
    account_id: int | None = None


class LandedCostCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    vendor_id: int | None = None
    date: date
    total_amount: float = Field(ge=0, default=0)
    split_method: str = Field(default="by_quantity", max_length=20)
    note: str | None = None
    lines: list[LandedCostLineCreate] = Field(default_factory=list)
    transfer_ids: list[int] = Field(default_factory=list)


class LandedCostRead(_ORM):
    id: int
    name: str
    state: str
    vendor_id: int | None = None
    date: date
    total_amount: float
    split_method: str
    note: str | None = None
    posted_at: datetime | None = None
    lines: list[LandedCostLineRead] = Field(default_factory=list)
    created_at: datetime


# ── Transfer Return / Backorder ────────────────────────────────────────


class ReturnLineItem(BaseModel):
    transfer_line_id: int
    quantity: float = Field(gt=0)


class ReturnCreate(BaseModel):
    lines: list[ReturnLineItem] = Field(min_length=1)

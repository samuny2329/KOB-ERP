"""Pydantic schemas for the WMS module API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.modules.wms.models import LOCATION_USAGES, PRODUCT_TYPES


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── UoM ────────────────────────────────────────────────────────────────


UomType = Literal["reference", "bigger", "smaller"]


class UomCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class UomCategoryRead(_ORM):
    id: int
    name: str


class UomCreate(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=60)
    uom_type: UomType = "reference"
    factor: float = 1.0
    rounding: float = 0.01


class UomRead(_ORM):
    id: int
    category_id: int
    name: str
    uom_type: str
    factor: float
    rounding: float
    active: bool


# ── Warehouse / Zone ──────────────────────────────────────────────────


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=8)
    name: str = Field(min_length=1, max_length=120)
    address: str | None = None


class WarehouseRead(_ORM):
    id: int
    code: str
    name: str
    address: str | None = None
    active: bool


class ZoneCreate(BaseModel):
    warehouse_id: int
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    note: str | None = None


class ZoneRead(_ORM):
    id: int
    warehouse_id: int
    code: str
    name: str
    color_hex: str | None = None
    note: str | None = None
    active: bool


# ── Location ───────────────────────────────────────────────────────────


LocationUsage = Literal["supplier", "customer", "internal", "inventory", "transit", "view", "production"]


class LocationCreate(BaseModel):
    warehouse_id: int | None = None
    parent_id: int | None = None
    zone_id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    usage: LocationUsage = "internal"
    barcode: str | None = Field(default=None, max_length=60)


class LocationRead(_ORM):
    id: int
    warehouse_id: int | None = None
    parent_id: int | None = None
    zone_id: int | None = None
    name: str
    complete_name: str | None = None
    usage: str
    barcode: str | None = None
    active: bool


# ── Product / Lot ──────────────────────────────────────────────────────


ProductType = Literal["consu", "service", "product"]


class ProductCategoryCreate(BaseModel):
    parent_id: int | None = None
    name: str = Field(min_length=1, max_length=120)


class ProductCategoryRead(_ORM):
    id: int
    parent_id: int | None = None
    name: str
    complete_name: str | None = None


class ProductCreate(BaseModel):
    default_code: str = Field(min_length=1, max_length=60)
    barcode: str | None = Field(default=None, max_length=60)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    type: ProductType = "product"
    category_id: int | None = None
    uom_id: int
    list_price: float = 0
    standard_price: float = 0


class ProductRead(_ORM):
    id: int
    default_code: str
    barcode: str | None = None
    name: str
    type: str
    category_id: int | None = None
    uom_id: int
    list_price: float
    standard_price: float
    active: bool
    created_at: datetime


class LotCreate(BaseModel):
    product_id: int
    name: str = Field(min_length=1, max_length=60)
    expiration_date: date | None = None
    note: str | None = None


class LotRead(_ORM):
    id: int
    product_id: int
    name: str
    expiration_date: date | None = None
    note: str | None = None


# Re-export usage tuples so callers/tests can import constants from here.
__all__ = [
    "UomCategoryCreate", "UomCategoryRead",
    "UomCreate", "UomRead", "UomType",
    "WarehouseCreate", "WarehouseRead",
    "ZoneCreate", "ZoneRead",
    "LocationCreate", "LocationRead", "LocationUsage", "LOCATION_USAGES",
    "ProductCategoryCreate", "ProductCategoryRead",
    "ProductCreate", "ProductRead", "ProductType", "PRODUCT_TYPES",
    "LotCreate", "LotRead",
]

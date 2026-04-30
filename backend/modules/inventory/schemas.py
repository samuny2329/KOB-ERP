"""Pydantic schemas for the inventory module API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── StockQuant ─────────────────────────────────────────────────────────


class StockQuantRead(_ORM):
    id: int
    location_id: int
    product_id: int
    lot_id: int | None = None
    quantity: float
    reserved_quantity: float


# ── Transfer types ─────────────────────────────────────────────────────


TransferDirection = Literal["inbound", "outbound", "internal"]


class TransferTypeCreate(BaseModel):
    warehouse_id: int
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=120)
    direction: TransferDirection
    sequence_prefix: str = Field(min_length=1, max_length=8)
    default_source_location_id: int | None = None
    default_dest_location_id: int | None = None


class TransferTypeRead(_ORM):
    id: int
    warehouse_id: int
    code: str
    name: str
    direction: str
    sequence_prefix: str
    default_source_location_id: int | None = None
    default_dest_location_id: int | None = None


# ── Transfer / Line ────────────────────────────────────────────────────


class TransferLineCreate(BaseModel):
    product_id: int
    uom_id: int
    quantity_demand: float = Field(gt=0)
    lot_id: int | None = None
    source_location_id: int | None = None
    dest_location_id: int | None = None


class TransferLineRead(_ORM):
    id: int
    transfer_id: int
    product_id: int
    uom_id: int
    lot_id: int | None = None
    source_location_id: int | None = None
    dest_location_id: int | None = None
    quantity_demand: float
    quantity_done: float


class TransferCreate(BaseModel):
    transfer_type_id: int
    source_location_id: int
    dest_location_id: int
    origin: str | None = None
    scheduled_date: datetime | None = None
    note: str | None = None
    lines: list[TransferLineCreate] = Field(default_factory=list, min_length=0)


class TransferRead(_ORM):
    id: int
    name: str
    transfer_type_id: int
    state: str
    source_location_id: int
    dest_location_id: int
    origin: str | None = None
    scheduled_date: datetime | None = None
    done_date: datetime | None = None
    note: str | None = None
    lines: list[TransferLineRead] = Field(default_factory=list)
    created_at: datetime

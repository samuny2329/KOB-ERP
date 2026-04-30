"""Pydantic schemas for cycle-count endpoints."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


SessionType = Literal["full", "cycle"]
AdjustmentState = Literal["pending", "approved", "rejected"]


class CountSessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    session_type: SessionType = "cycle"
    warehouse_id: int
    responsible_id: int | None = None
    date_start: date | None = None
    date_end: date | None = None
    variance_threshold_pct: float = 2.0
    note: str | None = None


class CountSessionRead(_ORM):
    id: int
    name: str
    state: str
    session_type: str
    warehouse_id: int
    responsible_id: int | None = None
    date_start: date | None = None
    date_end: date | None = None
    variance_threshold_pct: float
    note: str | None = None
    created_at: datetime


class CountTaskCreate(BaseModel):
    session_id: int
    location_id: int
    product_id: int | None = None
    assigned_user_id: int | None = None
    expected_qty: float = 0


class CountTaskRead(_ORM):
    id: int
    session_id: int
    state: str
    location_id: int
    product_id: int | None = None
    assigned_user_id: int | None = None
    expected_qty: float
    counted_qty: float
    variance: float


class CountEntryCreate(BaseModel):
    task_id: int
    product_id: int
    lot_id: int | None = None
    qty: float = Field(ge=0)


class CountEntryRead(_ORM):
    id: int
    task_id: int
    product_id: int
    lot_id: int | None = None
    qty: float
    scanned_at: datetime


class CountAdjustmentRead(_ORM):
    id: int
    session_id: int
    task_id: int | None = None
    product_id: int
    location_id: int
    qty_variance: float
    reason: str | None = None
    state: str
    approved_by: int | None = None
    approved_at: datetime | None = None

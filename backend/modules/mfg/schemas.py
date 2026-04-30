"""Pydantic schemas for the manufacturing module."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BomLineCreate(_Base):
    component_id: int
    qty: float
    uom_id: int | None = None
    notes: str | None = None


class BomLineRead(_Base):
    id: int
    component_id: int
    qty: float
    uom_id: int | None


class BomCreate(_Base):
    code: str
    name: str
    product_id: int
    output_qty: float = 1
    uom_id: int | None = None
    lines: list[BomLineCreate] = []


class BomRead(_Base):
    id: int
    code: str
    name: str
    product_id: int
    output_qty: float
    active: bool
    lines: list[BomLineRead] = []


class MoCreate(_Base):
    number: str
    bom_id: int
    product_id: int
    qty_planned: float
    scheduled_date: date | None = None
    warehouse_id: int | None = None
    notes: str | None = None


class MoRead(_Base):
    id: int
    number: str
    bom_id: int
    product_id: int
    qty_planned: float
    qty_produced: float
    state: str
    scheduled_date: date | None


class WorkOrderCreate(_Base):
    mo_id: int
    operation_name: str
    assigned_user_id: int | None = None
    planned_start: datetime | None = None
    notes: str | None = None


class WorkOrderRead(_Base):
    id: int
    mo_id: int
    operation_name: str
    state: str
    assigned_user_id: int | None
    planned_start: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None


class SubconReconLineCreate(_Base):
    product_id: int
    qty_sent: float
    qty_returned: float = 0
    unit_cost: float = 0


class SubconReconCreate(_Base):
    number: str
    subcon_vendor_id: int
    send_date: date | None = None
    expected_return_date: date | None = None
    notes: str | None = None
    lines: list[SubconReconLineCreate] = []


class SubconReconRead(_Base):
    id: int
    number: str
    subcon_vendor_id: int
    state: str
    send_date: date | None
    expected_return_date: date | None
    actual_return_date: date | None

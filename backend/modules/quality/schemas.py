"""Pydantic schemas for quality checks and defects."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


CheckState = Literal["pending", "passed", "failed", "skipped"]
Severity = Literal["minor", "major", "critical"]


class CheckCreate(BaseModel):
    order_id: int
    order_line_id: int | None = None
    product_id: int
    lot_id: int | None = None
    expected_qty: float = 0
    check_notes: str | None = None


class DefectRead(_ORM):
    id: int
    check_id: int
    product_id: int
    defect_type: str
    severity: str
    description: str | None = None
    root_cause: str | None = None
    action_taken: str | None = None
    occurred_at: datetime


class CheckRead(_ORM):
    id: int
    state: str
    order_id: int
    order_line_id: int | None = None
    product_id: int
    lot_id: int | None = None
    expected_qty: float
    checked_by_id: int | None = None
    checked_at: datetime | None = None
    check_notes: str | None = None
    defects: list[DefectRead] = Field(default_factory=list)
    created_at: datetime


class DefectCreate(BaseModel):
    check_id: int
    product_id: int
    defect_type: str = Field(min_length=1, max_length=60)
    severity: Severity = "minor"
    description: str | None = None
    root_cause: str | None = None
    action_taken: str | None = None

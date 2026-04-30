"""Pydantic schemas for the ops module."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── BoxSize ──────────────────────────────────────────────────────────


class BoxSizeCreate(_Base):
    code: str
    name: str
    length_cm: float
    width_cm: float
    height_cm: float
    max_weight_kg: float
    cost: float = 0
    active: bool = True


class BoxSizeRead(_Base):
    id: int
    code: str
    name: str
    length_cm: float
    width_cm: float
    height_cm: float
    max_weight_kg: float
    cost: float
    active: bool


class BoxUsageCreate(_Base):
    usage_date: date
    warehouse_id: int
    box_size_id: int
    qty_used: int = 0
    qty_wasted: int = 0


class BoxUsageRead(_Base):
    id: int
    usage_date: date
    warehouse_id: int
    box_size_id: int
    qty_used: int
    qty_wasted: int


# ── Platform ──────────────────────────────────────────────────────────


class PlatformConfigCreate(_Base):
    platform: str
    shop_name: str
    shop_id: str | None = None
    active: bool = True


class PlatformConfigRead(_Base):
    id: int
    platform: str
    shop_name: str
    shop_id: str | None
    active: bool


class PlatformOrderLineRead(_Base):
    id: int
    sku: str
    product_name: str | None
    qty: int
    unit_price: float


class PlatformOrderCreate(_Base):
    platform: str
    external_order_id: str
    platform_config_id: int | None = None
    buyer_name: str | None = None
    buyer_phone: str | None = None
    shipping_address: str | None = None
    total_amount: float = 0
    currency: str = "THB"
    ordered_at: datetime | None = None
    warehouse_id: int | None = None


class PlatformOrderRead(_Base):
    id: int
    platform: str
    external_order_id: str
    status: str
    buyer_name: str | None
    total_amount: float
    currency: str
    ordered_at: datetime | None
    warehouse_id: int | None
    outbound_order_id: int | None
    lines: list[PlatformOrderLineRead] = []


# ── KPI ───────────────────────────────────────────────────────────────


class WorkerKpiCreate(_Base):
    user_id: int
    kpi_date: date
    picks_completed: int = 0
    packs_completed: int = 0
    orders_shipped: int = 0
    errors_reported: int = 0
    active_minutes: int = 0
    accuracy_pct: float | None = None
    throughput_score: float | None = None


class WorkerKpiRead(_Base):
    id: int
    user_id: int
    kpi_date: date
    picks_completed: int
    packs_completed: int
    orders_shipped: int
    errors_reported: int
    active_minutes: int
    accuracy_pct: float | None
    throughput_score: float | None


class KpiTargetCreate(_Base):
    warehouse_id: int
    metric_name: str
    target_value: float
    warning_pct: float = 80.0
    critical_pct: float = 60.0


class KpiTargetRead(_Base):
    id: int
    warehouse_id: int
    metric_name: str
    target_value: float
    warning_pct: float
    critical_pct: float


class KpiAlertRead(_Base):
    id: int
    warehouse_id: int | None
    user_id: int | None
    metric_name: str
    severity: str
    message: str
    actual_value: float | None
    target_value: float | None
    resolved: bool
    resolved_at: datetime | None
    created_at: datetime


# ── Reports ───────────────────────────────────────────────────────────


class DailyReportRead(_Base):
    id: int
    report_date: date
    warehouse_id: int
    orders_received: int
    orders_shipped: int
    orders_pending: int
    picks_completed: int
    transfers_done: int
    quality_checks: int
    quality_fails: int
    boxes_used: int
    total_revenue: float


class MonthlyReportRead(_Base):
    id: int
    year: int
    month: int
    warehouse_id: int
    orders_received: int
    orders_shipped: int
    avg_processing_hours: float | None
    return_rate_pct: float | None
    total_revenue: float
    top_sku: str | None

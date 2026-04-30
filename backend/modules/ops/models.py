"""Operations models — box catalogue, platform orders, worker KPI, reports."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel


class PlatformType(str, Enum):
    shopee = "shopee"
    lazada = "lazada"
    tiktok = "tiktok"
    manual = "manual"


class PlatformOrderStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    shipped = "shipped"
    completed = "completed"
    cancelled = "cancelled"
    returned = "returned"


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


# ── Box catalogue ──────────────────────────────────────────────────────


class BoxSize(BaseModel):
    """Packaging box sizes with dimensional weight and cost."""

    __tablename__ = "box_size"
    __table_args__ = ({"schema": "ops"},)

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    length_cm: Mapped[float] = mapped_column(Float, nullable=False)
    width_cm: Mapped[float] = mapped_column(Float, nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    max_weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def volume_cm3(self) -> float:
        return self.length_cm * self.width_cm * self.height_cm

    @property
    def dimensional_weight_kg(self) -> float:
        return self.volume_cm3 / 5000


class BoxUsage(BaseModel):
    """Daily box consumption tracking per warehouse."""

    __tablename__ = "box_usage"
    __table_args__ = ({"schema": "ops"},)

    usage_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=False
    )
    box_size_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ops.box_size.id", ondelete="CASCADE"), nullable=False
    )
    qty_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qty_wasted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    box_size: Mapped[BoxSize] = relationship(lazy="select")


# ── Platform integrations ─────────────────────────────────────────────


class PlatformConfig(BaseModel):
    """API credentials / webhook config per e-commerce platform."""

    __tablename__ = "platform_config"
    __table_args__ = ({"schema": "ops"},)

    platform: Mapped[str] = mapped_column(String(40), nullable=False)
    shop_name: Mapped[str] = mapped_column(String(180), nullable=False)
    shop_id: Mapped[str | None] = mapped_column(String(120))
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    webhook_secret: Mapped[str | None] = mapped_column(String(256))


class PlatformOrder(BaseModel):
    """Inbound order from Shopee / Lazada / TikTok."""

    __tablename__ = "platform_order"
    __table_args__ = ({"schema": "ops"},)

    platform: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_order_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    platform_config_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ops.platform_config.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    buyer_name: Mapped[str | None] = mapped_column(String(240))
    buyer_phone: Mapped[str | None] = mapped_column(String(40))
    shipping_address: Mapped[str | None] = mapped_column(Text)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(10), default="THB")
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL")
    )
    outbound_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("outbound.order.id", ondelete="SET NULL")
    )
    raw_payload: Mapped[str | None] = mapped_column(Text)

    config: Mapped[PlatformConfig | None] = relationship(lazy="select")


class PlatformOrderLine(BaseModel):
    """Line items within a platform order."""

    __tablename__ = "platform_order_line"
    __table_args__ = ({"schema": "ops"},)

    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ops.platform_order.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(120), nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(240))
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="SET NULL")
    )

    order: Mapped[PlatformOrder] = relationship(back_populates="lines", lazy="select")


PlatformOrder.lines = relationship(
    PlatformOrderLine, back_populates="order", lazy="select", cascade="all, delete-orphan"
)


# ── Worker KPI ─────────────────────────────────────────────────────────


class WorkerKpi(BaseModel):
    """Daily performance snapshot per worker."""

    __tablename__ = "worker_kpi"
    __table_args__ = ({"schema": "ops"},)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kpi_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    picks_completed: Mapped[int] = mapped_column(Integer, default=0)
    packs_completed: Mapped[int] = mapped_column(Integer, default=0)
    orders_shipped: Mapped[int] = mapped_column(Integer, default=0)
    errors_reported: Mapped[int] = mapped_column(Integer, default=0)
    active_minutes: Mapped[int] = mapped_column(Integer, default=0)
    accuracy_pct: Mapped[float | None] = mapped_column(Float)
    throughput_score: Mapped[float | None] = mapped_column(Float)


class KpiTarget(BaseModel):
    """KPI target thresholds per warehouse (used to fire alerts)."""

    __tablename__ = "kpi_target"
    __table_args__ = ({"schema": "ops"},)

    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(80), nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    warning_pct: Mapped[float] = mapped_column(Float, default=80.0)
    critical_pct: Mapped[float] = mapped_column(Float, default=60.0)


class KpiAlert(BaseModel):
    """Triggered KPI alerts (auto-cleared when resolved)."""

    __tablename__ = "kpi_alert"
    __table_args__ = ({"schema": "ops"},)

    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL")
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL")
    )
    metric_name: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="warning", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    actual_value: Mapped[float | None] = mapped_column(Float)
    target_value: Mapped[float | None] = mapped_column(Float)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ── Daily / Monthly reports ───────────────────────────────────────────


class DailyReport(BaseModel):
    """Aggregated daily warehouse summary (pre-computed)."""

    __tablename__ = "daily_report"
    __table_args__ = ({"schema": "ops"},)

    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=False
    )
    orders_received: Mapped[int] = mapped_column(Integer, default=0)
    orders_shipped: Mapped[int] = mapped_column(Integer, default=0)
    orders_pending: Mapped[int] = mapped_column(Integer, default=0)
    picks_completed: Mapped[int] = mapped_column(Integer, default=0)
    transfers_done: Mapped[int] = mapped_column(Integer, default=0)
    quality_checks: Mapped[int] = mapped_column(Integer, default=0)
    quality_fails: Mapped[int] = mapped_column(Integer, default=0)
    boxes_used: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[float] = mapped_column(Numeric(16, 2), default=0)


class MonthlyReport(BaseModel):
    """Aggregated monthly warehouse summary."""

    __tablename__ = "monthly_report"
    __table_args__ = ({"schema": "ops"},)

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=False
    )
    orders_received: Mapped[int] = mapped_column(Integer, default=0)
    orders_shipped: Mapped[int] = mapped_column(Integer, default=0)
    avg_processing_hours: Mapped[float | None] = mapped_column(Float)
    return_rate_pct: Mapped[float | None] = mapped_column(Float)
    total_revenue: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    top_sku: Mapped[str | None] = mapped_column(String(120))

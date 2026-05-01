"""Group module — company hierarchy, KPI rollup, inventory pool."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel


class CompanyGroup(BaseModel):
    """Holding group — aggregate entity for a set of related companies."""

    __tablename__ = "company_group"
    __table_args__ = ({"schema": "grp"},)

    name: Mapped[str] = mapped_column(String(240), nullable=False)
    root_company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )
    consolidation_currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    memberships: Mapped[list["CompanyMembership"]] = relationship(
        back_populates="group", lazy="select", cascade="all, delete-orphan"
    )


class CompanyMembership(BaseModel):
    """Many-to-many: company → group with ownership detail."""

    __tablename__ = "company_membership"
    __table_args__ = (
        UniqueConstraint("company_id", "group_id", name="uq_company_membership"),
        {"schema": "grp"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company_group.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(30), default="subsidiary", nullable=False)  # parent/subsidiary/affiliate
    ownership_pct: Mapped[float] = mapped_column(Numeric(6, 3), default=0, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    group: Mapped[CompanyGroup] = relationship(back_populates="memberships", lazy="select")


class GroupKpiRollup(BaseModel):
    """Append-only KPI record per company per period — aggregated up the tree."""

    __tablename__ = "group_kpi_rollup"
    __table_args__ = (
        UniqueConstraint("company_id", "period", "metric_name", name="uq_kpi_company_period_metric"),
        {"schema": "grp"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. 2025-04
    metric_name: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GroupKpiConfig(BaseModel):
    """Defines which KPIs to track and how to aggregate them."""

    __tablename__ = "group_kpi_config"
    __table_args__ = (
        UniqueConstraint("metric_name", name="uq_kpi_config_metric"),
        {"schema": "grp"},
    )

    metric_name: Mapped[str] = mapped_column(String(80), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0, nullable=False)
    aggregation: Mapped[str] = mapped_column(String(10), default="sum", nullable=False)  # sum/avg/last
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class InventoryPool(BaseModel):
    """Virtual inventory pool spanning multiple company warehouses."""

    __tablename__ = "inventory_pool"
    __table_args__ = ({"schema": "grp"},)

    pool_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    routing_strategy: Mapped[str] = mapped_column(
        String(30), default="priority", nullable=False
    )  # priority/lowest_cost/nearest/balance_load
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    members: Mapped[list["InventoryPoolMember"]] = relationship(
        back_populates="pool", lazy="select", cascade="all, delete-orphan"
    )


class InventoryPoolMember(BaseModel):
    """Company warehouse participation in an inventory pool."""

    __tablename__ = "inventory_pool_member"
    __table_args__ = (
        UniqueConstraint("pool_id", "company_id", name="uq_pool_company"),
        {"schema": "grp"},
    )

    pool_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.inventory_pool.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL"), nullable=True
    )

    pool: Mapped[InventoryPool] = relationship(back_populates="members", lazy="select")

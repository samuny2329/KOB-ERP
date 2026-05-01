"""Group module partner models — Group Customer/Vendor 360, SKU bridge, rebate engine."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel


class GroupCustomerProfile(BaseModel):
    """Cross-company customer master — aggregates all local Customer records."""

    __tablename__ = "group_customer_profile"
    __table_args__ = ({"schema": "grp"},)

    group_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    group_credit_limit: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    group_ltv_score: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    links: Mapped[list["GroupCustomerLink"]] = relationship(
        back_populates="profile", lazy="select", cascade="all, delete-orphan"
    )


class GroupCustomerLink(BaseModel):
    """Maps a local company-specific Customer to a GroupCustomerProfile."""

    __tablename__ = "group_customer_link"
    __table_args__ = (
        UniqueConstraint("group_customer_id", "company_id", "customer_id", name="uq_group_customer_link"),
        {"schema": "grp"},
    )

    group_customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.group_customer_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.customer.id", ondelete="CASCADE"), nullable=False
    )

    profile: Mapped[GroupCustomerProfile] = relationship(back_populates="links", lazy="select")


class GroupVendorProfile(BaseModel):
    """Cross-company vendor master — aggregates all local Vendor records."""

    __tablename__ = "group_vendor_profile"
    __table_args__ = ({"schema": "grp"},)

    group_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    lifetime_spend: Mapped[float] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    ytd_spend: Mapped[float] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    group_otd_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    group_quality_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=100, nullable=False)
    group_score: Mapped[float] = mapped_column(Numeric(5, 2), default=100, nullable=False)

    links: Mapped[list["GroupVendorLink"]] = relationship(
        back_populates="profile", lazy="select", cascade="all, delete-orphan"
    )
    rebate_tiers: Mapped[list["VolumeRebateTier"]] = relationship(
        back_populates="vendor_profile", lazy="select", cascade="all, delete-orphan"
    )


class GroupVendorLink(BaseModel):
    """Maps a local company-specific Vendor to a GroupVendorProfile."""

    __tablename__ = "group_vendor_link"
    __table_args__ = (
        UniqueConstraint("group_vendor_id", "company_id", "vendor_id", name="uq_group_vendor_link"),
        {"schema": "grp"},
    )

    group_vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.group_vendor_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False
    )
    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="CASCADE"), nullable=False
    )

    profile: Mapped[GroupVendorProfile] = relationship(back_populates="links", lazy="select")


class VolumeRebateTier(BaseModel):
    """Spend threshold → rebate rate for a group vendor."""

    __tablename__ = "volume_rebate_tier"
    __table_args__ = ({"schema": "grp"},)

    group_vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.group_vendor_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tier_label: Mapped[str] = mapped_column(String(40), nullable=False)
    min_spend: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    rebate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), default="annual", nullable=False)  # monthly/quarterly/annual

    vendor_profile: Mapped[GroupVendorProfile] = relationship(back_populates="rebate_tiers", lazy="select")


class VolumeRebateAccrual(BaseModel):
    """Accrued rebate snapshot per period for a group vendor."""

    __tablename__ = "volume_rebate_accrual"
    __table_args__ = (
        UniqueConstraint("group_vendor_id", "period", name="uq_rebate_accrual_vendor_period"),
        {"schema": "grp"},
    )

    group_vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.group_vendor_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. 2025-Q2
    accrued_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    tier_matched: Mapped[str | None] = mapped_column(String(40), nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CrossCompanySkuBridge(BaseModel):
    """Master SKU that maps to local product IDs across companies."""

    __tablename__ = "cross_company_sku_bridge"
    __table_args__ = ({"schema": "grp"},)

    master_sku: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    master_name: Mapped[str] = mapped_column(String(240), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    items: Mapped[list["SkuBridgeItem"]] = relationship(
        back_populates="bridge", lazy="select", cascade="all, delete-orphan"
    )


class SkuBridgeItem(BaseModel):
    """Per-company local product reference inside a SKU bridge."""

    __tablename__ = "sku_bridge_item"
    __table_args__ = (
        UniqueConstraint("bridge_id", "company_id", name="uq_sku_bridge_item"),
        {"schema": "grp"},
    )

    bridge_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.cross_company_sku_bridge.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False
    )
    local_sku: Mapped[str | None] = mapped_column(String(80), nullable=True)

    bridge: Mapped[CrossCompanySkuBridge] = relationship(back_populates="items", lazy="select")

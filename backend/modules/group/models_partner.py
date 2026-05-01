"""Group-wide partner profiles + volume rebates.

Why these are KOB-exclusive:
  * Odoo / SAP B1 / NetSuite all model "customer" per legal entity.  When
    one buyer purchases from three sister companies they appear as three
    rows; AR, credit, LTV are all per-company.
  * Volume rebates from vendors (kickbacks at tier thresholds) require
    spend aggregation across companies — usually done in spreadsheets.

This module gives both partners (customer + vendor) a *group profile*
that aggregates per-company links into one record with combined credit /
spend / LTV / rebate accruals.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel


# ── Cross-company customer profile ─────────────────────────────────────


class CrossCompanyCustomer(BaseModel):
    """Group-level customer record — aggregates per-company `sales.customer`.

    A buyer might have a separate `sales.customer` row in each operating
    company (e.g. Lazada Mall as a customer of A, B, and C).  This profile
    is the single source of truth for group credit, group LTV, group
    payment behaviour, and the FK target for marketing / loyalty
    integrations that don't care which legal entity sold the goods.
    """

    __tablename__ = "cross_company_customer"
    __table_args__ = ({"schema": "grp"},)

    group_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    customer_group: Mapped[str] = mapped_column(String(20), default="regular", nullable=False)
    # Group-wide credit applied across every member company.
    group_credit_limit: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    group_credit_consumed: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    group_ltv_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    links: Mapped[list["CrossCompanyCustomerLink"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CrossCompanyCustomerLink(BaseModel):
    """Maps a CrossCompanyCustomer to its per-company `sales.customer` rows."""

    __tablename__ = "cross_company_customer_link"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "company_id", name="uq_xc_customer_link"
        ),
        UniqueConstraint(
            "company_id", "local_customer_id", name="uq_xc_customer_local"
        ),
        {"schema": "grp"},
    )

    profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("grp.cross_company_customer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    local_customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.customer.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped[CrossCompanyCustomer] = relationship(back_populates="links", lazy="select")


# ── Cross-company vendor profile ───────────────────────────────────────


class CrossCompanyVendor(BaseModel):
    """Group-level vendor record — aggregates per-company `purchase.vendor`.

    Holds the negotiated volume-rebate tiers + lifetime group spend so a
    single tier engine can compute kickbacks regardless of which company
    issued the PO.
    """

    __tablename__ = "cross_company_vendor"
    __table_args__ = ({"schema": "grp"},)

    group_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payment_currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    # Aggregated KPIs — refreshed by the analytics job.
    lifetime_spend: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    ytd_spend: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    group_otd_pct: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    group_quality_pct: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    group_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    links: Mapped[list["CrossCompanyVendorLink"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CrossCompanyVendorLink(BaseModel):
    __tablename__ = "cross_company_vendor_link"
    __table_args__ = (
        UniqueConstraint("profile_id", "company_id", name="uq_xc_vendor_link"),
        UniqueConstraint("company_id", "local_vendor_id", name="uq_xc_vendor_local"),
        {"schema": "grp"},
    )

    profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("grp.cross_company_vendor.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    local_vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped[CrossCompanyVendor] = relationship(back_populates="links", lazy="select")


# ── Volume rebate tracker ──────────────────────────────────────────────


REBATE_PERIODS = ("monthly", "quarterly", "annual")


class VolumeRebateTier(BaseModel):
    """One step in a vendor's rebate ladder.

    Example tiers for vendor "Acme":
      0      < spend < 5M    →  0% rebate
      5M    < spend < 10M   →  3% rebate
      10M   < spend         →  5% rebate

    Tiers are stored independently — `rank_tiers()` picks the highest
    qualifying tier given the running spend.
    """

    __tablename__ = "volume_rebate_tier"
    __table_args__ = (
        UniqueConstraint(
            "vendor_profile_id", "period_kind", "min_spend", name="uq_rebate_tier"
        ),
        {"schema": "grp"},
    )

    vendor_profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("grp.cross_company_vendor.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_kind: Mapped[str] = mapped_column(String(20), default="annual", nullable=False)
    min_spend: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    max_spend: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    rebate_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class VolumeRebateAccrual(BaseModel):
    """Snapshot of accrued rebate for a vendor over a window.

    Created/refreshed by the analytics job; one row per (vendor, period)
    so historical rebates remain queryable.
    """

    __tablename__ = "volume_rebate_accrual"
    __table_args__ = (
        UniqueConstraint(
            "vendor_profile_id", "period_kind", "period_start", name="uq_rebate_accrual"
        ),
        {"schema": "grp"},
    )

    vendor_profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("grp.cross_company_vendor.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_group_spend: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    matched_tier_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0, nullable=False)
    accrued_rebate: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    settled_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

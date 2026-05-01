"""Group governance — SKU bridge, brand licenses, transfer pricing,
approval substitution.

These are operational policy tables that the rest of the system
consults at decision time.  Adding a row changes behaviour for the
whole group without touching transactional data.
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


# ── Cross-company SKU bridge ───────────────────────────────────────────


class SkuBridge(BaseModel):
    """One physical product → many local SKU codes.

    Use case: KOB sells "Cream 50ml" but each company has a different
    `wms.product` row — Lazada listing is "L-CRM50", Shopee is "S-CR50".
    The bridge lets a single platform sync rule resolve any incoming
    platform SKU to the right local product per company.
    """

    __tablename__ = "sku_bridge"
    __table_args__ = ({"schema": "grp"},)

    master_sku: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(60), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["SkuBridgeMember"]] = relationship(
        back_populates="bridge",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SkuBridgeMember(BaseModel):
    """Per-company resolution of a master SKU."""

    __tablename__ = "sku_bridge_member"
    __table_args__ = (
        UniqueConstraint("bridge_id", "company_id", name="uq_sku_bridge_company"),
        UniqueConstraint(
            "company_id", "local_product_id", name="uq_sku_bridge_local"
        ),
        {"schema": "grp"},
    )

    bridge_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("grp.sku_bridge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="CASCADE"), nullable=False
    )
    local_product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False
    )
    local_sku: Mapped[str | None] = mapped_column(String(60), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    bridge: Mapped[SkuBridge] = relationship(back_populates="members", lazy="select")


# ── Brand license registry ─────────────────────────────────────────────


LICENSE_SCOPES = ("exclusive", "non_exclusive", "co_exclusive")


class BrandLicense(BaseModel):
    """Right to sell a brand / product line under a company.

    Use case: KOB-Cosmetics owns the "Glow" brand and licenses it to
    KOB-Distribution for the Thai market with a 7% royalty.
    """

    __tablename__ = "brand_license"
    __table_args__ = (
        UniqueConstraint(
            "brand_code", "licensed_to_company_id", "valid_from",
            name="uq_brand_license_window",
        ),
        {"schema": "grp"},
    )

    brand_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    brand_name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    licensed_to_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    territory: Mapped[str] = mapped_column(String(80), default="TH", nullable=False)
    license_scope: Mapped[str] = mapped_column(String(20), default="non_exclusive", nullable=False)
    royalty_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0, nullable=False)
    minimum_royalty_per_period: Mapped[float] = mapped_column(
        Numeric(16, 2), default=0, nullable=False
    )
    period_kind: Mapped[str] = mapped_column(String(20), default="quarterly", nullable=False)
    product_category_ids: Mapped[dict | None] = mapped_column(JSON, default=None)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Transfer-pricing agreements ────────────────────────────────────────


PRICING_METHODS = ("cost_plus", "fixed", "market", "resale_minus", "tnmm")


class TransferPricingAgreement(BaseModel):
    """Predefined pricing rule for inter-company transactions.

    When `sales.IntercompanyTransfer` fires for a (from, to, category)
    combo, it consults this table for the agreed method + percentage.
    Tax authorities require documentation of these rules (TNMM, etc.)
    so we keep validity windows + the chosen method explicit.
    """

    __tablename__ = "transfer_pricing_agreement"
    __table_args__ = (
        UniqueConstraint(
            "from_company_id",
            "to_company_id",
            "product_category_id",
            "valid_from",
            name="uq_transfer_pricing_window",
        ),
        {"schema": "grp"},
    )

    from_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    to_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    product_category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product_category.id", ondelete="CASCADE"), nullable=True
    )
    method: Mapped[str] = mapped_column(String(20), default="cost_plus", nullable=False)
    markup_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0, nullable=False)
    fixed_price: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    documentation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Approval substitution ──────────────────────────────────────────────


class ApprovalSubstitution(BaseModel):
    """Fallback approver rule when the primary is unavailable.

    Use case: CFO of company A is on leave 10–20 May; designate CFO of
    company B as fallback.  Approval engine consults this table after
    looking up the matrix rule.
    """

    __tablename__ = "approval_substitution"
    __table_args__ = (
        UniqueConstraint(
            "primary_user_id", "valid_from", name="uq_approval_substitution"
        ),
        {"schema": "grp"},
    )

    primary_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("core.user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fallback_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="CASCADE"), nullable=False
    )
    primary_company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="SET NULL"), nullable=True
    )
    document_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

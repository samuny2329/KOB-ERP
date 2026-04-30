"""Sales advanced models — Odoo 19 parity + KOB-exclusive features.

Odoo 19 parity:
  - SalesTeam (crm.team)
  - Pricelist + PricelistRule (product.pricelist + .item)
  - LostReason (crm.lost.reason)
  - ReturnOrder + ReturnLine (RMA — community add-on shape)

KOB-exclusive (not in Odoo / SAP / Oracle):
  - MultiPlatformOrder — one SO fulfilled from many Shopee/Lazada/TikTok shops
  - ChannelMargin — per-channel margin snapshot (after fees, returns)
  - CustomerLtvSnapshot — rolling 90d spend / repeat / return rate
  - IntercompanyTransfer — auto-mirror PO when SO ships from another company

Multi-company link:
  Most transactional models (Pricelist, SalesTeam, ReturnOrder,
  IntercompanyTransfer, ChannelMargin) carry company_id so a single
  deployment can serve multiple legal entities.
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
from backend.core.workflow import WorkflowMixin


# ── Odoo 19 parity ──────────────────────────────────────────────────────


class SalesTeam(BaseModel):
    """Sales team — manager + default commission for the members.

    Mirrors Odoo `crm.team`.  Each `Customer.sales_team_id` and
    `SalesOrder.sales_team_id` points here.
    """

    __tablename__ = "sales_team"
    __table_args__ = ({"schema": "sales"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="SET NULL"), nullable=True
    )
    manager_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    default_commission_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    target_revenue: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


PRICELIST_BASIS = ("list_price", "standard_cost", "other_pricelist")
RULE_TYPES = ("fixed", "discount_pct", "formula")


class Pricelist(BaseModel):
    """Named pricing definition — applied to customers (and groups).

    A pricelist holds many ``PricelistRule`` rows that fire by qty / product /
    category match in declared sequence order.  ``base`` says where the
    starting price comes from before applying the rule's adjustment.
    """

    __tablename__ = "pricelist"
    __table_args__ = ({"schema": "sales"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="SET NULL"), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    base: Mapped[str] = mapped_column(String(30), default="list_price", nullable=False)
    customer_group: Mapped[str | None] = mapped_column(String(20), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rules: Mapped[list["PricelistRule"]] = relationship(
        back_populates="pricelist",
        lazy="select",
        cascade="all, delete-orphan",
    )


class PricelistRule(BaseModel):
    """One rule on a Pricelist — matches by product / category / qty / dates.

    ``rule_type`` ∈ {fixed, discount_pct, formula}; the ``value`` field is
    interpreted accordingly.  Rules are applied in ascending ``sequence``;
    first match wins.
    """

    __tablename__ = "pricelist_rule"
    __table_args__ = ({"schema": "sales"},)

    pricelist_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales.pricelist.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=True
    )
    product_category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product_category.id", ondelete="CASCADE"), nullable=True
    )
    min_qty: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    rule_type: Mapped[str] = mapped_column(String(20), default="discount_pct", nullable=False)
    value: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    pricelist: Mapped[Pricelist] = relationship(back_populates="rules", lazy="select")


class LostReason(BaseModel):
    """Why a quotation didn't convert.  Mirrors Odoo `crm.lost.reason`."""

    __tablename__ = "lost_reason"
    __table_args__ = ({"schema": "sales"},)

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Returns / RMA ──────────────────────────────────────────────────────


class ReturnOrder(BaseModel, WorkflowMixin):
    """Return / RMA header — links back to a SalesOrder.

    State flow:
      draft → received → restocked   (terminal)
                       ↘ scrapped     (terminal)
              ↓
      cancelled    (from draft only)
    """

    __tablename__ = "return_order"
    __table_args__ = ({"schema": "sales"},)

    initial_state = "draft"
    allowed_transitions = {
        "draft": {"received", "cancelled"},
        "received": {"restocked", "scrapped"},
        "restocked": set(),
        "scrapped": set(),
        "cancelled": set(),
    }

    ref: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    sales_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales.sales_order.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False
    )
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    receipt_location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="SET NULL"), nullable=True
    )
    refund_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["ReturnLine"]] = relationship(
        back_populates="return_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# Structured reason codes feed into the product KPI dashboard.
RETURN_REASONS = (
    "wrong_item",       # We sent the wrong SKU
    "damaged",          # Damaged in transit
    "defective",        # Manufacturing defect
    "not_as_described", # Mismatch vs listing
    "buyer_remorse",    # Changed mind
    "expired",          # Past expiry
    "duplicate",        # Customer ordered twice
    "other",
)


class ReturnLine(BaseModel):
    """Per-product detail of a return.

    ``reason_code`` feeds the product quality KPI (``ops.kpi_alert`` rules
    can fire on `product.return_rate_pct > threshold`).
    """

    __tablename__ = "return_line"
    __table_args__ = ({"schema": "sales"},)

    return_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales.return_order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    so_line_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sales.so_line.id", ondelete="SET NULL"), nullable=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    qty_returned: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    qty_restocked: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    qty_scrapped: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(30), default="other", nullable=False)
    reason_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    refund_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )

    return_order: Mapped[ReturnOrder] = relationship(back_populates="lines", lazy="select")


# ── KOB-exclusive ──────────────────────────────────────────────────────


class MultiPlatformOrder(BaseModel):
    """Bridge row: one SalesOrder ↔ many ops.platform_order rows.

    Lets a single SO be fulfilled from multiple marketplace shops in one
    pick/pack run.  ``commission_deducted`` is the platform fee KOB
    surrenders (pre-computed at confirm time so margin reports are stable
    even if a marketplace adjusts fees retroactively).
    """

    __tablename__ = "multi_platform_order"
    __table_args__ = (
        UniqueConstraint(
            "sales_order_id", "platform_order_id", name="uq_multi_platform_pair"
        ),
        {"schema": "sales"},
    )

    sales_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales.sales_order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ops.platform_order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commission_pct: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    commission_deducted: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    shipping_subsidy: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ChannelMargin(BaseModel):
    """Per-channel margin snapshot — refreshable summary."""

    __tablename__ = "channel_margin"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "channel", "period_start", name="uq_channel_margin_window"
        ),
        {"schema": "sales"},
    )

    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    gross_revenue: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    cogs: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    platform_fees: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    shipping_cost: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    return_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    net_margin: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    margin_pct: Mapped[float] = mapped_column(Float, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CustomerLtvSnapshot(BaseModel):
    """Append-only — historical LTV scores per customer.

    Computed as ``net_revenue_90d × repeat_rate × (1 − return_rate)``.
    Refreshed by a scheduled job; old rows kept for trend analysis.
    """

    __tablename__ = "customer_ltv_snapshot"
    __table_args__ = ({"schema": "sales"},)

    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales.customer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    revenue_90d: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    order_count_90d: Mapped[int] = mapped_column(Integer, default=0)
    repeat_rate: Mapped[float] = mapped_column(Float, default=0)
    return_rate: Mapped[float] = mapped_column(Float, default=0)
    avg_order_value: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    score: Mapped[float] = mapped_column(Float, default=0)
    breakdown: Mapped[dict | None] = mapped_column(JSON, default=None)


class IntercompanyTransfer(BaseModel, WorkflowMixin):
    """Mirror PO when a SalesOrder ships from a sibling company's warehouse.

    State flow:
      draft → mirrored → settled    (terminal)
        ↓        ↓
        └────────┴── cancelled       (terminal)

    Created automatically by ``create_intercompany_mirror_po`` when
    ``sales_order.company_id != warehouse.company_id``.  The bridge row
    holds both the originating SO and the auto-created PO on the
    warehouse-owning company.
    """

    __tablename__ = "intercompany_transfer"
    __table_args__ = ({"schema": "sales"},)

    initial_state = "draft"
    allowed_transitions = {
        "draft": {"mirrored", "cancelled"},
        "mirrored": {"settled", "cancelled"},
        "settled": set(),
        "cancelled": set(),
    }

    sales_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales.sales_order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    so_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    fulfillment_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    mirror_po_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase.purchase_order.id", ondelete="SET NULL"), nullable=True
    )
    transfer_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    transfer_pricing_method: Mapped[str] = mapped_column(
        String(20), default="cost_plus", nullable=False
    )
    transfer_pricing_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

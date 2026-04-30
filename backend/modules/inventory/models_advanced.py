"""Advanced inventory models — Odoo 19 parity features.

Covers:
  - Package / Pallet (multi-level logistics units)
  - Putaway Rules (auto-route incoming goods to sub-locations)
  - Reorder Rules (min/max replenishment triggers)
  - Stock Valuation Layer (FIFO/AVCO cost tracking per move)
  - Scrap Order (write-off flow)
  - Landed Cost (allocation of freight/duty to product cost)
"""

from __future__ import annotations

from datetime import date, datetime

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


# ── Package / Pallet ──────────────────────────────────────────────────


class PackageType(BaseModel):
    """Pallet / carton / envelope type — defines dimensions & max weight."""

    __tablename__ = "package_type"
    __table_args__ = ({"schema": "inventory"},)

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    width_cm: Mapped[float | None] = mapped_column(Float)
    length_cm: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    max_weight_kg: Mapped[float | None] = mapped_column(Float)
    barcode: Mapped[str | None] = mapped_column(String(60), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Package(BaseModel):
    """Physical container (box/pallet) that groups stock move lines.

    Odoo 19 equivalent: stock.quant.package.
    A package can be nested inside another package (pallet of cartons).
    """

    __tablename__ = "package"
    __table_args__ = ({"schema": "inventory"},)

    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    package_type_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.package_type.id", ondelete="SET NULL")
    )
    location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="SET NULL")
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.package.id", ondelete="SET NULL")
    )
    company_id: Mapped[int | None] = mapped_column(BigInteger)  # future multi-company
    owner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL")
    )
    weight_kg: Mapped[float] = mapped_column(Float, default=0)

    package_type: Mapped[PackageType | None] = relationship(lazy="select")


# ── Putaway Rules ─────────────────────────────────────────────────────


class PutawayRule(BaseModel):
    """Determines where to put incoming goods.

    Odoo 19 equivalent: stock.putaway.rule.
    Priority: product-specific > category-specific.
    When a transfer line arrives at ``location_id``, the rule redirects it
    to ``location_dest_id`` if product/category matches.
    """

    __tablename__ = "putaway_rule"
    __table_args__ = ({"schema": "inventory"},)

    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_dest_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=True
    )
    product_category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product_category.id", ondelete="CASCADE"), nullable=True
    )
    package_type_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.package_type.id", ondelete="SET NULL"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    capacity_count: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location: Mapped["backend.modules.wms.models.Location"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[location_id], lazy="select"
    )
    location_dest: Mapped["backend.modules.wms.models.Location"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[location_dest_id], lazy="select"
    )


# ── Reorder Rules ─────────────────────────────────────────────────────


class ReorderRule(BaseModel):
    """Min/Max replenishment rule.

    Odoo 19 equivalent: stock.warehouse.orderpoint.
    When on-hand qty falls below ``qty_min``, a replenishment is triggered
    to bring stock up to ``qty_max``.
    """

    __tablename__ = "reorder_rule"
    __table_args__ = (
        UniqueConstraint("product_id", "location_id", name="uq_reorder_product_location"),
        {"schema": "inventory"},
    )

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="CASCADE"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=False
    )
    qty_min: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    qty_max: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    qty_multiple: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=1)
    lead_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # last auto-trigger result
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_qty_ordered: Mapped[float | None] = mapped_column(Numeric(16, 4))


# ── Stock Valuation Layer ─────────────────────────────────────────────


class StockValuationLayer(BaseModel):
    """Cost layer for FIFO / AVCO valuation.

    Odoo 19 equivalent: stock.valuation.layer.
    One row per transfer line that moves a stockable product.
    Negative quantity = goods out (cost credit), positive = goods in (cost debit).
    """

    __tablename__ = "stock_valuation_layer"
    __table_args__ = ({"schema": "inventory"},)

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transfer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.transfer.id", ondelete="SET NULL"), nullable=True
    )
    transfer_line_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.transfer_line.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(16, 6), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    remaining_qty: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    remaining_value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(240))
    # Link to landed cost adjustment if applicable
    landed_cost_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.landed_cost.id", ondelete="SET NULL"), nullable=True
    )


# ── Scrap ─────────────────────────────────────────────────────────────


class ScrapOrder(BaseModel, WorkflowMixin):
    """Write-off of damaged / expired / unusable goods.

    Odoo 19 equivalent: stock.scrap.
    Validated scrap moves qty from source location to scrap location and
    creates a valuation layer entry (cost write-off).
    State: draft → done (terminal).
    """

    __tablename__ = "scrap_order"
    __table_args__ = ({"schema": "inventory"},)

    allowed_transitions = {
        "draft": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }

    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    package_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.package.id", ondelete="SET NULL"), nullable=True
    )
    uom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.uom.id", ondelete="RESTRICT"), nullable=False
    )
    scrap_qty: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    source_location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=False
    )
    scrap_location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    origin: Mapped[str | None] = mapped_column(String(120))
    scrap_reason: Mapped[str | None] = mapped_column(Text)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # cost at time of scrap
    unit_cost: Mapped[float] = mapped_column(Numeric(14, 6), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


# ── Landed Cost ───────────────────────────────────────────────────────


LANDED_COST_STATES = ["draft", "posted", "cancelled"]
SPLIT_METHODS = ("equal", "by_quantity", "by_weight", "by_volume", "by_current_cost")


class LandedCost(BaseModel, WorkflowMixin):
    """Allocation of freight, duty, insurance to incoming goods cost.

    Odoo 19 equivalent: stock.landed.cost.
    When posted, creates StockValuationLayer adjustments for each product
    on the linked transfers, split by the chosen split_method.
    """

    __tablename__ = "landed_cost"
    __table_args__ = ({"schema": "inventory"},)

    allowed_transitions = {
        "draft": {"posted", "cancelled"},
        "posted": set(),
        "cancelled": set(),
    }

    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    vendor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    split_method: Mapped[str] = mapped_column(String(20), nullable=False, default="by_quantity")
    note: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lines: Mapped[list["LandedCostLine"]] = relationship(
        back_populates="landed_cost", lazy="select", cascade="all, delete-orphan"
    )
    transfer_links: Mapped[list["LandedCostTransfer"]] = relationship(
        back_populates="landed_cost", lazy="select", cascade="all, delete-orphan"
    )


class LandedCostLine(BaseModel):
    """One cost component within a landed cost (e.g. freight, duty)."""

    __tablename__ = "landed_cost_line"
    __table_args__ = ({"schema": "inventory"},)

    landed_cost_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory.landed_cost.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    split_method: Mapped[str] = mapped_column(String(20), nullable=False, default="by_quantity")
    account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )

    landed_cost: Mapped[LandedCost] = relationship(back_populates="lines", lazy="select")


class LandedCostTransfer(BaseModel):
    """Links a landed cost to one or more validated transfers (receipts)."""

    __tablename__ = "landed_cost_transfer"
    __table_args__ = (
        UniqueConstraint("landed_cost_id", "transfer_id", name="uq_lc_transfer"),
        {"schema": "inventory"},
    )

    landed_cost_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory.landed_cost.id", ondelete="CASCADE"), nullable=False
    )
    transfer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory.transfer.id", ondelete="CASCADE"), nullable=False
    )

    landed_cost: Mapped[LandedCost] = relationship(back_populates="transfer_links", lazy="select")

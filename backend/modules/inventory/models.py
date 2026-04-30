"""Inventory models — stock quants + transfers + transfer lines.

Mirrors Odoo's `stock.quant` / `stock.picking` / `stock.move` concepts but
re-implemented from scratch with idiomatic SQLAlchemy 2.0.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
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
from backend.modules.wms.models import Location, Lot, Product, Uom, Warehouse


class StockQuant(BaseModel):
    """Live on-hand snapshot.  One row per (location, product, lot)."""

    __tablename__ = "stock_quant"
    __table_args__ = (
        UniqueConstraint(
            "location_id", "product_id", "lot_id", name="uq_quant_location_product_lot"
        ),
        {"schema": "inventory"},
    )

    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    reserved_quantity: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)

    location: Mapped[Location] = relationship()
    product: Mapped[Product] = relationship()
    lot: Mapped[Lot | None] = relationship()

    @property
    def available_quantity(self) -> float:
        return float(self.quantity) - float(self.reserved_quantity)


# ── Transfer types ─────────────────────────────────────────────────────


TRANSFER_DIRECTIONS = ("inbound", "outbound", "internal")


class TransferType(BaseModel):
    """Operational templates — e.g. WH/IN, WH/OUT, WH/INT.

    Drives default source/destination locations and sequence prefixes.
    """

    __tablename__ = "transfer_type"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_transfer_type_code"),
        {"schema": "inventory"},
    )

    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    sequence_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    default_source_location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="SET NULL"), nullable=True
    )
    default_dest_location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="SET NULL"), nullable=True
    )

    warehouse: Mapped[Warehouse] = relationship()


# ── Transfer + Lines ───────────────────────────────────────────────────


class Transfer(BaseModel, WorkflowMixin):
    """A movement of goods between two locations.  Header.

    State flow (allowed_transitions):
      draft → confirmed → done
      draft → cancelled
      confirmed → cancelled
    """

    __tablename__ = "transfer"
    __table_args__ = ({"schema": "inventory"},)

    allowed_transitions = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }

    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    transfer_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory.transfer_type.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=False
    )
    dest_location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=False
    )
    origin: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Odoo 19 additions
    is_return: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    origin_transfer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.transfer.id", ondelete="SET NULL"), nullable=True
    )
    backorder_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.transfer.id", ondelete="SET NULL"), nullable=True
    )
    responsible_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    carrier_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.courier.id", ondelete="SET NULL"), nullable=True
    )
    carrier_tracking_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)

    transfer_type: Mapped[TransferType] = relationship()
    source_location: Mapped[Location] = relationship(foreign_keys=[source_location_id])
    dest_location: Mapped[Location] = relationship(foreign_keys=[dest_location_id])
    origin_transfer: Mapped["Transfer | None"] = relationship(
        foreign_keys=[origin_transfer_id], remote_side="Transfer.id"
    )
    lines: Mapped[list["TransferLine"]] = relationship(
        back_populates="transfer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TransferLine(BaseModel):
    """One line of a Transfer — one product, optionally one lot."""

    __tablename__ = "transfer_line"
    __table_args__ = ({"schema": "inventory"},)

    transfer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory.transfer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    uom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.uom.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    source_location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=True
    )
    dest_location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=True
    )
    quantity_demand: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    quantity_done: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    quantity_reserved: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    # Package grouping (Odoo 19)
    package_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.package.id", ondelete="SET NULL"), nullable=True
    )
    result_package_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory.package.id", ondelete="SET NULL"), nullable=True
    )

    transfer: Mapped[Transfer] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()
    uom: Mapped[Uom] = relationship()
    lot: Mapped[Lot | None] = relationship()

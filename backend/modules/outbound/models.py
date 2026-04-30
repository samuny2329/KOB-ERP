"""Outbound transaction models.

Mirrors the operational flow from KOB-WMS::

    Order  ─pending→ picking → picked → packing → packed → shipped
            └────────────────────────cancelled────────────────────┘

DispatchBatch groups packed orders that hand off together to one courier.
ScanItem is a single barcode scan event recorded during dispatch.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin
from backend.modules.wms.models import Lot, Product
from backend.modules.wms.models_outbound import Courier


class Order(BaseModel, WorkflowMixin):
    """Customer order being fulfilled.

    State flow::

        pending → picking → picked → packing → packed → shipped
        any non-terminal → cancelled
    """

    __tablename__ = "order"
    __table_args__ = ({"schema": "outbound"},)

    initial_state = "pending"
    allowed_transitions = {
        "pending": {"picking", "cancelled"},
        "picking": {"picked", "cancelled"},
        "picked": {"packing", "cancelled"},
        "packing": {"packed", "cancelled"},
        "packed": {"shipped", "cancelled"},
        "shipped": set(),
        "cancelled": set(),
    }

    ref: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="SET NULL"), nullable=True, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    courier_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.courier.id", ondelete="SET NULL"), nullable=True
    )
    awb: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    box_barcode: Mapped[str | None] = mapped_column(String(80), nullable=True)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    sla_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pick_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pack_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    packed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    picker_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    packer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    shipper_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )

    courier: Mapped[Courier | None] = relationship()
    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class OrderLine(BaseModel):
    """One product line on an outbound Order."""

    __tablename__ = "order_line"
    __table_args__ = ({"schema": "outbound"},)

    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbound.order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    qty_expected: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    qty_picked: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    qty_packed: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    sku: Mapped[str | None] = mapped_column(String(60), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    order: Mapped[Order] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()
    lot: Mapped[Lot | None] = relationship()


class DispatchBatch(BaseModel, WorkflowMixin):
    """Grouped handoff to a single courier — driver signs once for many orders.

    State flow::

        draft → scanning → dispatched
        draft / scanning → cancelled
    """

    __tablename__ = "dispatch_batch"
    __table_args__ = ({"schema": "outbound"},)

    initial_state = "draft"
    allowed_transitions = {
        "draft": {"scanning", "cancelled"},
        "scanning": {"dispatched", "cancelled"},
        "dispatched": set(),
        "cancelled": set(),
    }

    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    courier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.courier.id", ondelete="RESTRICT"), nullable=False
    )
    work_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receiver_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatched_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    courier: Mapped[Courier] = relationship()
    scans: Mapped[list["ScanItem"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ScanItem(BaseModel):
    """A single barcode scan during a dispatch batch."""

    __tablename__ = "scan_item"
    __table_args__ = ({"schema": "outbound"},)

    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbound.dispatch_batch.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("outbound.order.id", ondelete="SET NULL"),
        nullable=True,
    )
    barcode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    scanned_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )

    batch: Mapped[DispatchBatch] = relationship(back_populates="scans")
    order: Mapped[Order | None] = relationship()

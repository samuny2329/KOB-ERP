"""Manufacturing models — BoM, work orders, subcon reconciliation."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


class BomTemplate(BaseModel):
    """Bill of Materials header."""

    __tablename__ = "bom_template"
    __table_args__ = ({"schema": "mfg"},)

    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    output_qty: Mapped[float] = mapped_column(Numeric(14, 4), default=1)
    uom_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("wms.uom.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    lines: Mapped[list["BomLine"]] = relationship(
        back_populates="bom", lazy="select", cascade="all, delete-orphan"
    )


class BomLine(BaseModel):
    """Component line in a BoM."""

    __tablename__ = "bom_line"
    __table_args__ = ({"schema": "mfg"},)

    bom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.bom_template.id", ondelete="CASCADE"), nullable=False
    )
    component_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    uom_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("wms.uom.id"))
    notes: Mapped[str | None] = mapped_column(String(240))

    bom: Mapped[BomTemplate] = relationship(back_populates="lines", lazy="select")


MO_STATES = ["draft", "confirmed", "in_progress", "done", "cancelled"]


class ManufacturingOrder(BaseModel, WorkflowMixin):
    """Manufacturing order — consumes components, produces finished goods."""

    __tablename__ = "manufacturing_order"
    __table_args__ = ({"schema": "mfg"},)

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    bom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.bom_template.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    qty_planned: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    qty_produced: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)

    work_orders: Mapped[list["WorkOrder"]] = relationship(
        back_populates="mo", lazy="select", cascade="all, delete-orphan"
    )


class WorkOrder(BaseModel, WorkflowMixin):
    """Individual operation step in an MO."""

    __tablename__ = "work_order"
    __table_args__ = ({"schema": "mfg"},)

    mo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.manufacturing_order.id", ondelete="CASCADE"), nullable=False
    )
    operation_name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    assigned_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL")
    )
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    mo: Mapped[ManufacturingOrder] = relationship(back_populates="work_orders", lazy="select")


class SubconVendor(BaseModel):
    """Subcontractor vendor (extends base vendor concept for mfg)."""

    __tablename__ = "subcon_vendor"
    __table_args__ = ({"schema": "mfg"},)

    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    specialty: Mapped[str | None] = mapped_column(String(160))
    lead_days: Mapped[int] = mapped_column(Integer, default=7)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


RECON_STATES = ["draft", "sent", "reconciling", "done", "disputed"]


class SubconRecon(BaseModel, WorkflowMixin):
    """Subcontractor reconciliation — matches sent qty vs returned qty."""

    __tablename__ = "subcon_recon"
    __table_args__ = ({"schema": "mfg"},)

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    subcon_vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.subcon_vendor.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    send_date: Mapped[date | None] = mapped_column(Date)
    expected_return_date: Mapped[date | None] = mapped_column(Date)
    actual_return_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["SubconReconLine"]] = relationship(
        back_populates="recon", lazy="select", cascade="all, delete-orphan"
    )


class SubconReconLine(BaseModel):
    """Per-product line in a subcon reconciliation."""

    __tablename__ = "subcon_recon_line"
    __table_args__ = ({"schema": "mfg"},)

    recon_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.subcon_recon.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    qty_sent: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    qty_returned: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    qty_variance: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    variance_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    recon: Mapped[SubconRecon] = relationship(back_populates="lines", lazy="select")

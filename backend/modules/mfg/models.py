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
    # Odoo 19 parity: versioning
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    # Routing reference
    routing_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mfg.routing.id", ondelete="SET NULL"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    lines: Mapped[list["BomLine"]] = relationship(
        back_populates="bom", lazy="select", cascade="all, delete-orphan"
    )


class BomLine(BaseModel):
    """Component / by-product / phantom line in a BoM."""

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
    # Odoo 19 parity: line type + by-product support
    line_type: Mapped[str] = mapped_column(String(10), default="component", nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    # KOB-exclusive: country of origin for ASEAN/export compliance
    country_of_origin: Mapped[str | None] = mapped_column(String(3))  # ISO 3166-1 alpha-3
    hs_code: Mapped[str | None] = mapped_column(String(15))           # Harmonized System code
    notes: Mapped[str | None] = mapped_column(String(240))

    bom: Mapped[BomTemplate] = relationship(back_populates="lines", lazy="select")


MO_STATES = ["draft", "confirmed", "in_progress", "to_close", "done", "cancelled"]

# BOM line types (Odoo 19 parity)
BOM_LINE_TYPES = ("component", "byproduct", "phantom")


class BomVersion(BaseModel):
    """Versioned snapshot of a BOM for change control.

    Odoo 19 parity: each major BOM change creates a new version with
    effectivity dates. The active version is used for new MOs.
    """

    __tablename__ = "bom_version"
    __table_args__ = ({"schema": "mfg"},)

    bom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.bom_template.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ManufacturingOrder(BaseModel, WorkflowMixin):
    """Manufacturing order — consumes components, produces finished goods."""

    __tablename__ = "manufacturing_order"
    __table_args__ = ({"schema": "mfg"},)

    allowed_transitions = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"in_progress", "cancelled"},
        "in_progress": {"to_close", "cancelled"},
        "to_close": {"done", "in_progress"},
        "done": set(),
        "cancelled": set(),
    }

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    bom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.bom_template.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    qty_planned: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    qty_produced: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    qty_scrap: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL")
    )
    # Finished goods lot/serial assignment (Odoo 19 parity)
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    # Cost tracking (Odoo 19 parity)
    material_cost: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    labor_cost: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    overhead_cost: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    # Subcon link (KOB enhancement)
    subcon_recon_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mfg.subcon_recon.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    work_orders: Mapped[list["WorkOrder"]] = relationship(
        back_populates="mo", lazy="select", cascade="all, delete-orphan"
    )


class WorkOrder(BaseModel, WorkflowMixin):
    """Individual operation step in an MO, linked to a work center."""

    __tablename__ = "work_order"
    __table_args__ = ({"schema": "mfg"},)

    allowed_transitions = {
        "draft": {"ready", "cancelled"},
        "ready": {"in_progress", "cancelled"},
        "in_progress": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }

    mo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.manufacturing_order.id", ondelete="CASCADE"), nullable=False
    )
    operation_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Work center link (Odoo 19 parity)
    work_center_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mfg.work_center.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    assigned_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL")
    )
    # Scheduling
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Time tracking (Odoo 19 parity)
    setup_duration: Mapped[int] = mapped_column(Integer, default=0)      # minutes
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    remaining_minutes: Mapped[int | None] = mapped_column(Integer)
    qty_production: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    # KOB-exclusive: shift
    shift_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mfg.production_shift.id", ondelete="SET NULL"), nullable=True
    )
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
    # KOB-exclusive: quality metrics auto-computed on recon done
    variance_rate: Mapped[float] = mapped_column(Float, default=0, nullable=False)  # avg qty_variance / qty_sent
    quality_score: Mapped[float] = mapped_column(Float, default=100, nullable=False)  # 0-100
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

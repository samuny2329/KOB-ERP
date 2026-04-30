"""Advanced manufacturing models — Odoo 19 parity + KOB-exclusive features.

Covers:
  - WorkCenter          : machine/station with capacity, efficiency, OEE
  - Routing             : ordered sequence of work center operations per BOM
  - RoutingOperation    : one step in a routing
  - MoComponentLine     : lot-tracked component consumption per MO
  - MoScrap             : scrap qty + reason during production
  - UnbuildOrder        : reverse production (disassemble → components)
  - ProductionShift     : shift-based scheduling (KOB-exclusive)
  - MoProductionSignal  : demand-driven MO suggestion from platform orders (KOB-exclusive)
  - BatchConsolidation  : group small orders into one production run (KOB-exclusive)
  - WorkCenterOee       : Overall Equipment Effectiveness snapshot per shift
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


# ── Work Centers (Odoo 19 parity) ─────────────────────────────────────


class WorkCenter(BaseModel):
    """Machine or station where manufacturing operations are performed.

    Odoo 19 equivalent: mrp.workcenter.
    ``capacity`` = number of parallel jobs it can handle.
    ``time_efficiency`` = 100 means 100% efficient; 80 means actual time = planned / 0.8.
    ``oee_target`` = target OEE percentage for KPI reporting.
    """

    __tablename__ = "work_center"
    __table_args__ = ({"schema": "mfg"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL"), nullable=True
    )
    capacity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    time_efficiency: Mapped[float] = mapped_column(Float, default=100.0)   # percent
    cost_per_hour: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    oee_target: Mapped[float] = mapped_column(Float, default=85.0)         # percent target
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


# ── Routing (Odoo 19 parity) ───────────────────────────────────────────


class Routing(BaseModel):
    """Ordered sequence of work center operations assigned to a BOM.

    Odoo 19 equivalent: mrp.routing / mrp.routing.workcenter.
    """

    __tablename__ = "routing"
    __table_args__ = ({"schema": "mfg"},)

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    operations: Mapped[list["RoutingOperation"]] = relationship(
        back_populates="routing", cascade="all, delete-orphan", lazy="select"
    )


class RoutingOperation(BaseModel):
    """One step in a routing — links a work center with a duration template."""

    __tablename__ = "routing_operation"
    __table_args__ = ({"schema": "mfg"},)

    routing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.routing.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    work_center_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.work_center.id", ondelete="RESTRICT"), nullable=False
    )
    default_duration: Mapped[int] = mapped_column(Integer, default=60)    # minutes
    setup_duration: Mapped[int] = mapped_column(Integer, default=0)       # minutes
    note: Mapped[str | None] = mapped_column(Text)

    routing: Mapped[Routing] = relationship(back_populates="operations", lazy="select")


# ── MO Component Lines (lot-tracked consumption) ──────────────────────


class MoComponentLine(BaseModel):
    """Actual component consumption per MO with lot tracking.

    Odoo 19 equivalent: stock.move (raw components).
    One row per component consumed, records which lot was actually used.
    """

    __tablename__ = "mo_component_line"
    __table_args__ = ({"schema": "mfg"},)

    mo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.manufacturing_order.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    uom_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("wms.uom.id"))
    qty_demand: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    qty_done: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    source_location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="SET NULL")
    )
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


# ── MO Scrap (Odoo 19 parity) ──────────────────────────────────────────


class MoScrap(BaseModel):
    """Scrap event recorded during production.

    Tracks which component was scrapped, quantity, reason,
    and updates MO.qty_scrap rolling total.
    """

    __tablename__ = "mo_scrap"
    __table_args__ = ({"schema": "mfg"},)

    mo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.manufacturing_order.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    qty: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    scrap_reason: Mapped[str | None] = mapped_column(String(240))
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    scrapped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ── Unbuild Orders (Odoo 19 parity) ───────────────────────────────────


class UnbuildOrder(BaseModel, WorkflowMixin):
    """Reverse a production — disassemble finished goods back to components.

    Odoo 19 equivalent: mrp.unbuild.
    State: draft → done (terminal).
    """

    __tablename__ = "unbuild_order"
    __table_args__ = ({"schema": "mfg"},)

    allowed_transitions = {
        "draft": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }

    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    bom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.bom_template.id", ondelete="RESTRICT"), nullable=False
    )
    mo_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mfg.manufacturing_order.id", ondelete="SET NULL"), nullable=True
    )
    qty: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="SET NULL")
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)


# ── Production Shifts (KOB-exclusive) ─────────────────────────────────


class ProductionShift(BaseModel):
    """Shift definition for a warehouse/work center (day/afternoon/night).

    KOB-exclusive: Thai factories typically run 2–3 shifts.
    Work orders are assigned to shifts for capacity planning.
    """

    __tablename__ = "production_shift"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_shift_warehouse_code"),
        {"schema": "mfg"},
    )

    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "D", "A", "N"
    name: Mapped[str] = mapped_column(String(60), nullable=False)  # Day / Afternoon / Night
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-23
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)    # 0-23
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Work Center OEE Snapshot (Odoo 19 + KOB-exclusive) ────────────────


class WorkCenterOee(BaseModel):
    """OEE (Overall Equipment Effectiveness) snapshot per work center per shift.

    OEE = Availability × Performance × Quality.
    Recorded at end of each shift by the shop floor system.
    """

    __tablename__ = "work_center_oee"
    __table_args__ = (
        UniqueConstraint("work_center_id", "oee_date", "shift_id", name="uq_oee_wc_date_shift"),
        {"schema": "mfg"},
    )

    work_center_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.work_center.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shift_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mfg.production_shift.id", ondelete="SET NULL"), nullable=True
    )
    oee_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_time: Mapped[int] = mapped_column(Integer, nullable=False)     # minutes
    available_time: Mapped[int] = mapped_column(Integer, nullable=False)   # after downtime
    run_time: Mapped[int] = mapped_column(Integer, nullable=False)         # actual production
    ideal_cycle_time: Mapped[float] = mapped_column(Float, default=0)      # min/unit
    total_units: Mapped[int] = mapped_column(Integer, default=0)
    good_units: Mapped[int] = mapped_column(Integer, default=0)
    # Computed
    availability: Mapped[float] = mapped_column(Float, default=0)   # available/planned * 100
    performance: Mapped[float] = mapped_column(Float, default=0)    # run/available * 100
    quality: Mapped[float] = mapped_column(Float, default=0)        # good/total * 100
    oee: Mapped[float] = mapped_column(Float, default=0)            # availability*performance*quality/10000


# ── Demand-driven MO Suggestion (KOB-exclusive) ───────────────────────


class MoProductionSignal(BaseModel):
    """Platform sales velocity → manufacturing order suggestion.

    KOB-exclusive: reads ops.platform_order data.
    When forecasted demand exceeds available finished goods + in-progress MOs,
    a new MO is suggested.
    """

    __tablename__ = "mo_production_signal"
    __table_args__ = ({"schema": "mfg"},)

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bom_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mfg.bom_template.id", ondelete="SET NULL"), nullable=True
    )
    platform: Mapped[str | None] = mapped_column(String(30))  # shopee | lazada | tiktok | all
    avg_daily_demand: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=3)
    current_stock: Mapped[float] = mapped_column(Float, default=0)
    wip_qty: Mapped[float] = mapped_column(Float, default=0)
    suggested_qty: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | converted | ignored
    converted_mo_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mfg.manufacturing_order.id", ondelete="SET NULL"), nullable=True
    )


# ── Batch Consolidation Engine (KOB-exclusive) ────────────────────────


class BatchConsolidation(BaseModel):
    """Suggestion to merge multiple small MOs into a single production run.

    KOB-exclusive: reduces setup time by consolidating same-product MOs
    within a time window. Estimated saving = setup_duration × (n-1).
    """

    __tablename__ = "batch_consolidation"
    __table_args__ = ({"schema": "mfg"},)

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | accepted | rejected
    total_mos: Mapped[int] = mapped_column(Integer, default=0)
    total_qty: Mapped[float] = mapped_column(Float, default=0)
    setup_saving_minutes: Mapped[int] = mapped_column(Integer, default=0)
    window_days: Mapped[int] = mapped_column(Integer, default=3)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL")
    )

    items: Mapped[list["BatchConsolidationItem"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="select"
    )


class BatchConsolidationItem(BaseModel):
    """One MO included in a batch consolidation proposal."""

    __tablename__ = "batch_consolidation_item"
    __table_args__ = ({"schema": "mfg"},)

    batch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.batch_consolidation.id", ondelete="CASCADE"), nullable=False
    )
    mo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mfg.manufacturing_order.id", ondelete="CASCADE"), nullable=False
    )

    batch: Mapped[BatchConsolidation] = relationship(back_populates="items", lazy="select")

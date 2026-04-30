"""Cycle-count models — session, task, entry, adjustment, snapshot.

Workflow at a glance::

    Session: draft → in_progress → reconciling → done   (cancelled from draft/in_progress)
       │
       └── Tasks: assigned → counting → submitted → verified → approved
              │
              └── Entries (1..n)  +  Adjustments (0..n)  +  Snapshot (1)
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin
from backend.modules.wms.models import Location, Lot, Product, Warehouse


class CountSession(BaseModel, WorkflowMixin):
    __tablename__ = "count_session"
    __table_args__ = ({"schema": "inventory"},)

    initial_state = "draft"
    allowed_transitions = {
        "draft": {"in_progress", "cancelled"},
        "in_progress": {"reconciling", "cancelled"},
        "reconciling": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }

    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String(10), nullable=False, default="cycle")
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    responsible_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    date_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    variance_threshold_pct: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    warehouse: Mapped[Warehouse] = relationship()
    tasks: Mapped[list["CountTask"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CountTask(BaseModel, WorkflowMixin):
    __tablename__ = "count_task"
    __table_args__ = ({"schema": "inventory"},)

    initial_state = "assigned"
    allowed_transitions = {
        "assigned": {"counting", "cancelled"},
        "counting": {"submitted", "cancelled"},
        "submitted": {"verified", "counting", "cancelled"},
        "verified": {"approved", "submitted"},
        "approved": set(),
        "cancelled": set(),
    }

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory.count_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="SET NULL"), nullable=True
    )
    assigned_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    expected_qty: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    verified_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[CountSession] = relationship(back_populates="tasks")
    location: Mapped[Location] = relationship()
    product: Mapped[Product | None] = relationship()
    entries: Mapped[list["CountEntry"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def counted_qty(self) -> float:
        return float(sum(float(e.qty) for e in self.entries or []))

    @property
    def variance(self) -> float:
        return self.counted_qty - float(self.expected_qty)


class CountEntry(BaseModel):
    __tablename__ = "count_entry"
    __table_args__ = ({"schema": "inventory"},)

    task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory.count_task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    qty: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    task: Mapped[CountTask] = relationship(back_populates="entries")
    product: Mapped[Product] = relationship()
    lot: Mapped[Lot | None] = relationship()


class CountAdjustment(BaseModel):
    """Variance reconciliation — proposed delta on stock for a count finding."""

    __tablename__ = "count_adjustment"
    __table_args__ = ({"schema": "inventory"},)

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory.count_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("inventory.count_task.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=False
    )
    qty_variance: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    state: Mapped[str] = mapped_column(String(15), nullable=False, default="pending")
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CountSnapshot(BaseModel):
    """Frozen before/after for an audit-grade record of the count outcome."""

    __tablename__ = "count_snapshot"
    __table_args__ = ({"schema": "inventory"},)

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventory.count_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.location.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    qty_before: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    qty_after: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

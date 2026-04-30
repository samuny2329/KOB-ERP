"""Quality module — outbound inspection checks and recorded defects.

Lives in the ``quality`` schema.  Quality checks are normally created
when an outbound Order enters ``packing`` and resolved before
``shipped``; downstream processes inspect ``state``.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin
from backend.modules.outbound.models import Order, OrderLine
from backend.modules.wms.models import Lot, Product


class Check(BaseModel, WorkflowMixin):
    """A single outgoing inspection on an outbound order or order line."""

    __tablename__ = "check"
    __table_args__ = ({"schema": "quality"},)

    initial_state = "pending"
    allowed_transitions = {
        "pending": {"passed", "failed", "skipped"},
        "passed": set(),
        "failed": set(),
        "skipped": set(),
    }

    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbound.order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_line_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("outbound.order_line.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    lot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.lot.id", ondelete="SET NULL"), nullable=True
    )
    expected_qty: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False, default=0)
    checked_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    order: Mapped[Order] = relationship()
    order_line: Mapped[OrderLine | None] = relationship()
    product: Mapped[Product] = relationship()
    lot: Mapped[Lot | None] = relationship()
    defects: Mapped[list["Defect"]] = relationship(
        back_populates="check",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# Severity scale matches Odoo + KOB-WMS convention: minor / major / critical.
DEFECT_SEVERITIES = ("minor", "major", "critical")


class Defect(BaseModel):
    """A specific defect recorded on a quality check."""

    __tablename__ = "defect"
    __table_args__ = ({"schema": "quality"},)

    check_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("quality.check.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    defect_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="minor")
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    check: Mapped[Check] = relationship(back_populates="defects")
    product: Mapped[Product] = relationship()

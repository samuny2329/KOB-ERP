"""Sales models — customers, quotations, sales orders, deliveries.

Extended in Phase 10 with company linkage, sales-team fields, pricing, and
KOB-exclusive promise-to-deliver / LTV / multi-platform support.
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


# Customer group buckets — used for pricelist routing + LTV cohorts.
CUSTOMER_GROUPS = ("vip", "regular", "wholesale", "retail")


class Customer(BaseModel):
    """Customer / client master.

    Phase 10 additions: company link, pricelist + sales team + payment term
    references, customer group, credit consumed/blocked state, LTV score.
    """

    __tablename__ = "customer"
    __table_args__ = ({"schema": "sales"},)

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    credit_limit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    payment_term_days: Mapped[int] = mapped_column(Integer, default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Phase 10 additions ────────────────────────────────────────────
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="SET NULL"), nullable=True, index=True
    )
    pricelist_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sales.pricelist.id", ondelete="SET NULL"), nullable=True
    )
    sales_team_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sales.sales_team.id", ondelete="SET NULL"), nullable=True
    )
    payment_term_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("purchase.payment_term.id", ondelete="SET NULL", use_alter=True, name="fk_customer_payment_term"),
        nullable=True,
    )
    customer_group: Mapped[str] = mapped_column(String(20), default="regular", nullable=False)
    credit_consumed: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    ltv_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    orders: Mapped[list["SalesOrder"]] = relationship(back_populates="customer", lazy="select")


SO_STATES = ["draft", "confirmed", "picking", "shipped", "invoiced", "cancelled"]


class SalesOrder(BaseModel, WorkflowMixin):
    """Sales order header."""

    __tablename__ = "sales_order"
    __table_args__ = ({"schema": "sales"},)

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.customer.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(10), default="THB")
    subtotal: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    shipping_address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="SET NULL")
    )
    platform_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ops.platform_order.id", ondelete="SET NULL")
    )

    # ── Phase 10 additions ────────────────────────────────────────────
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sales_team_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sales.sales_team.id", ondelete="SET NULL"), nullable=True
    )
    salesperson_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    commission_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    payment_term_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("purchase.payment_term.id", ondelete="SET NULL", use_alter=True, name="fk_so_payment_term"),
        nullable=True,
    )
    pricelist_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sales.pricelist.id", ondelete="SET NULL"), nullable=True
    )
    lost_reason_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sales.lost_reason.id", ondelete="SET NULL"), nullable=True
    )
    won_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    revision_of_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("sales.sales_order.id", ondelete="SET NULL", use_alter=True, name="fk_so_revision_of"),
        nullable=True,
    )
    # KOB-exclusive: promise-to-deliver
    promise_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    p2d_confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="orders", lazy="select")
    lines: Mapped[list["SoLine"]] = relationship(
        back_populates="order", lazy="select", cascade="all, delete-orphan"
    )


class SoLine(BaseModel):
    """Line item on a sales order."""

    __tablename__ = "so_line"
    __table_args__ = ({"schema": "sales"},)

    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.sales_order.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(240))
    qty_ordered: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    qty_delivered: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    uom_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("wms.uom.id"))
    subtotal: Mapped[float] = mapped_column(Numeric(16, 2), default=0)

    order: Mapped[SalesOrder] = relationship(back_populates="lines", lazy="select")


DELIVERY_STATES = ["draft", "confirmed", "done", "cancelled"]


class Delivery(BaseModel, WorkflowMixin):
    """Delivery order — outbound shipment to customer."""

    __tablename__ = "delivery"
    __table_args__ = ({"schema": "sales"},)

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    sales_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.sales_order.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    carrier: Mapped[str | None] = mapped_column(String(80))
    tracking_number: Mapped[str | None] = mapped_column(String(120))
    outbound_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("outbound.order.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["DeliveryLine"]] = relationship(
        back_populates="delivery", lazy="select", cascade="all, delete-orphan"
    )


class DeliveryLine(BaseModel):
    """Per-product shipped line."""

    __tablename__ = "delivery_line"
    __table_args__ = ({"schema": "sales"},)

    delivery_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.delivery.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    so_line_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sales.so_line.id", ondelete="SET NULL")
    )
    qty_done: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("wms.lot.id"))

    delivery: Mapped[Delivery] = relationship(back_populates="lines", lazy="select")

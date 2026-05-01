"""Advanced sales models — Odoo 19 parity + KOB-exclusive."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


class SalesTeam(BaseModel):
    """Sales team — groups salespersons under a common target."""

    __tablename__ = "sales_team"
    __table_args__ = ({"schema": "sales"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SalesPricelist(BaseModel):
    """Pricelist header — named price policy with optional currency."""

    __tablename__ = "sales_pricelist"
    __table_args__ = ({"schema": "sales"},)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )

    rules: Mapped[list["SalesPriceRule"]] = relationship(
        back_populates="pricelist", lazy="select", cascade="all, delete-orphan"
    )


class SalesPriceRule(BaseModel):
    """Individual price rule inside a pricelist."""

    __tablename__ = "sales_price_rule"
    __table_args__ = ({"schema": "sales"},)

    pricelist_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.sales_pricelist.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="CASCADE"), nullable=True
    )
    product_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    min_qty: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    pricelist: Mapped[SalesPricelist] = relationship(back_populates="rules", lazy="select")


class RmaOrder(BaseModel, WorkflowMixin):
    """Return Merchandise Authorization."""

    __tablename__ = "rma_order"
    __table_args__ = ({"schema": "sales"},)

    allowed_transitions: dict = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"received", "cancelled"},
        "received": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    so_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.sales_order.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["RmaLine"]] = relationship(
        back_populates="rma", lazy="select", cascade="all, delete-orphan"
    )


class RmaLine(BaseModel):
    """Single product return line inside an RMA."""

    __tablename__ = "rma_line"
    __table_args__ = ({"schema": "sales"},)

    rma_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.rma_order.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    qty_requested: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    qty_received: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    return_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)

    rma: Mapped[RmaOrder] = relationship(back_populates="lines", lazy="select")


class QuotationTemplate(BaseModel):
    """Reusable quotation template with pre-filled product lines."""

    __tablename__ = "quotation_template"
    __table_args__ = ({"schema": "sales"},)

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    lines: Mapped[list["QuotationTemplateLine"]] = relationship(
        back_populates="template", lazy="select", cascade="all, delete-orphan"
    )


class QuotationTemplateLine(BaseModel):
    """Product line inside a quotation template."""

    __tablename__ = "quotation_template_line"
    __table_args__ = ({"schema": "sales"},)

    template_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.quotation_template.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[float] = mapped_column(Numeric(14, 4), default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)

    template: Mapped[QuotationTemplate] = relationship(back_populates="lines", lazy="select")


# ── KOB-Exclusive ──────────────────────────────────────────────────────


class PlatformFeeRule(BaseModel):
    """Platform commission fee rate per e-commerce channel."""

    __tablename__ = "platform_fee_rule"
    __table_args__ = (
        UniqueConstraint("platform", "company_id", "effective_from", name="uq_platform_fee_rule"),
        {"schema": "sales"},
    )

    platform: Mapped[str] = mapped_column(String(30), nullable=False)  # shopee/lazada/tiktok/etc
    fee_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )


class SoMarginLine(BaseModel):
    """Margin snapshot captured at SO confirmation — immutable audit record."""

    __tablename__ = "so_margin_line"
    __table_args__ = ({"schema": "sales"},)

    so_line_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.so_line.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cogs: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    platform_fee: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    gross_margin: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    margin_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EtaxInvoiceRef(BaseModel):
    """Thai e-Tax invoice reference linked to a confirmed SO."""

    __tablename__ = "etax_invoice_ref"
    __table_args__ = (
        UniqueConstraint("etax_number", "company_id", name="uq_etax_number_company"),
        {"schema": "sales"},
    )

    so_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.sales_order.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    etax_number: Mapped[str] = mapped_column(String(80), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revenue_dept_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )


class IntercompanySalesOrder(BaseModel):
    """IC-SO linkage — mirrors an outbound SO as a PO in the target company."""

    __tablename__ = "intercompany_sales_order"
    __table_args__ = ({"schema": "sales"},)

    from_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    to_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    so_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.sales_order.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    po_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase.purchase_order.id", ondelete="SET NULL"), nullable=True
    )
    transfer_price_rule_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.transfer_price_rule.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

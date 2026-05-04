"""Advanced accounting models — Odoo 19 parity + KOB-exclusive Thai tax."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


# ── Fiscal Year ────────────────────────────────────────────────────────


class FiscalYear(BaseModel):
    """Accounting fiscal year — controls period locking."""

    __tablename__ = "fiscal_year"
    __table_args__ = (
        UniqueConstraint("name", "company_id", name="uq_fiscal_year_name_company"),
        {"schema": "accounting"},
    )

    name: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2025"
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # open/closed
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )


# ── Analytic ───────────────────────────────────────────────────────────


class AnalyticAccount(BaseModel):
    """Analytic account — secondary dimension for cost/profit tracking."""

    __tablename__ = "analytic_account"
    __table_args__ = (
        UniqueConstraint("code", "company_id", name="uq_analytic_account_code_company"),
        {"schema": "accounting"},
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan: Mapped[str] = mapped_column(String(30), default="project", nullable=False)  # project/dept/product/other
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AnalyticLine(BaseModel):
    """Single analytic distribution line linked to a journal entry line."""

    __tablename__ = "analytic_line"
    __table_args__ = ({"schema": "accounting"},)

    analytic_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounting.analytic_account.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    journal_entry_line_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.journal_entry_line.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )


# ── Bank Reconciliation ────────────────────────────────────────────────


class BankStatement(BaseModel, WorkflowMixin):
    """Bank statement import for reconciliation."""

    __tablename__ = "bank_statement"
    __table_args__ = ({"schema": "accounting"},)

    allowed_transitions: dict = {
        "draft": {"posted", "cancelled"},
        "posted": {"reconciled", "cancelled"},
        "reconciled": set(),
        "cancelled": set(),
    }

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    journal_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounting.journal.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    balance_start: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    balance_end: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["BankStatementLine"]] = relationship(
        back_populates="statement", lazy="select", cascade="all, delete-orphan"
    )


class BankStatementLine(BaseModel):
    """Individual transaction in a bank statement."""

    __tablename__ = "bank_statement_line"
    __table_args__ = ({"schema": "accounting"},)

    statement_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounting.bank_statement.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    partner_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # customer/vendor
    partner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    journal_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.journal_entry.id", ondelete="SET NULL"), nullable=True
    )

    statement: Mapped[BankStatement] = relationship(back_populates="lines", lazy="select")


# ── Customer Invoices ──────────────────────────────────────────────────


class CustomerInvoice(BaseModel, WorkflowMixin):
    """Customer invoice — receivable document from confirmed SO."""

    __tablename__ = "customer_invoice"
    __table_args__ = ({"schema": "accounting"},)

    allowed_transitions: dict = {
        "draft": {"posted", "cancelled"},
        "posted": {"paid", "cancelled"},
        "paid": set(),
        "cancelled": set(),
    }

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales.customer.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    so_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sales.sales_order.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    journal_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.journal_entry.id", ondelete="SET NULL"), nullable=True
    )
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["CustomerInvoiceLine"]] = relationship(
        back_populates="invoice", lazy="select", cascade="all, delete-orphan"
    )


class CustomerInvoiceLine(BaseModel):
    """Line item on a customer invoice."""

    __tablename__ = "customer_invoice_line"
    __table_args__ = ({"schema": "accounting"},)

    invoice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounting.customer_invoice.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(14, 4), default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=7.0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )
    analytic_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.analytic_account.id", ondelete="SET NULL"), nullable=True
    )

    invoice: Mapped[CustomerInvoice] = relationship(back_populates="lines", lazy="select")


# ── Vendor Bills ───────────────────────────────────────────────────────


class VendorBill(BaseModel, WorkflowMixin):
    """Vendor bill — payable document linked to a PO receipt."""

    __tablename__ = "vendor_bill"
    __table_args__ = ({"schema": "accounting"},)

    allowed_transitions: dict = {
        "draft": {"posted", "cancelled"},
        "posted": {"paid", "cancelled"},
        "paid": set(),
        "cancelled": set(),
    }

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase.vendor.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    po_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase.purchase_order.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    wht_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    journal_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.journal_entry.id", ondelete="SET NULL"), nullable=True
    )
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["VendorBillLine"]] = relationship(
        back_populates="bill", lazy="select", cascade="all, delete-orphan"
    )


class VendorBillLine(BaseModel):
    """Line item on a vendor bill."""

    __tablename__ = "vendor_bill_line"
    __table_args__ = ({"schema": "accounting"},)

    bill_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounting.vendor_bill.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(14, 4), default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=7.0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )
    analytic_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.analytic_account.id", ondelete="SET NULL"), nullable=True
    )

    bill: Mapped[VendorBill] = relationship(back_populates="lines", lazy="select")


# ── KOB-Exclusive: Thai Tax Reports ───────────────────────────────────


class ThaiVatReport(BaseModel):
    """Monthly VAT summary for ภพ.30 filing — auto-aggregated from posted invoices/bills."""

    __tablename__ = "thai_vat_report"
    __table_args__ = (
        UniqueConstraint("company_id", "period_month", "period_year", name="uq_vat_report_company_period"),
        {"schema": "accounting"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_vat_output: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    total_vat_input: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    net_vat: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)  # draft/filed
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rd_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)  # Revenue Dept submission ref


class ThaiPnd1Report(BaseModel):
    """Monthly employee WHT summary for ภงด.1 filing."""

    __tablename__ = "thai_pnd1_report"
    __table_args__ = (
        UniqueConstraint("company_id", "period_month", "period_year", name="uq_pnd1_report_company_period"),
        {"schema": "accounting"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_employees: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_income: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    total_wht: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rd_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)


class AccountingClosingEntry(BaseModel):
    """Year-end closing entry — zeroes out P&L accounts to retained earnings."""

    __tablename__ = "accounting_closing_entry"
    __table_args__ = (
        UniqueConstraint("fiscal_year_id", "company_id", name="uq_closing_entry_fy_company"),
        {"schema": "accounting"},
    )

    fiscal_year_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounting.fiscal_year.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    journal_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.journal_entry.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

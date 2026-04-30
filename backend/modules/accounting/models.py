"""Accounting models — chart of accounts, journals, double-entry bookkeeping."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


class AccountType(str):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    revenue = "revenue"
    expense = "expense"
    cogs = "cogs"


class Account(BaseModel):
    """Chart of accounts — one row per account code."""

    __tablename__ = "account"
    __table_args__ = ({"schema": "accounting"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL")
    )
    currency: Mapped[str] = mapped_column(String(10), default="THB")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reconcilable: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    children: Mapped[list["Account"]] = relationship(
        "Account", foreign_keys=[parent_id], lazy="select"
    )


class Journal(BaseModel):
    """Accounting journal — groups related entries (Sales, Purchases, Cash, etc.)."""

    __tablename__ = "journal"
    __table_args__ = ({"schema": "accounting"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    journal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    default_debit_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL")
    )
    default_credit_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    entries: Mapped[list["JournalEntry"]] = relationship(back_populates="journal", lazy="select")


JE_STATES = ["draft", "posted", "cancelled"]


class JournalEntry(BaseModel, WorkflowMixin):
    """Journal entry (voucher) — must have balanced debit/credit lines."""

    __tablename__ = "journal_entry"
    __table_args__ = ({"schema": "accounting"},)

    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    journal_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounting.journal.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="SET NULL"), nullable=True, index=True
    )
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    memo: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_model: Mapped[str | None] = mapped_column(String(80))
    source_id: Mapped[int | None] = mapped_column(BigInteger)

    journal: Mapped[Journal] = relationship(back_populates="entries", lazy="select")
    lines: Mapped[list["JournalEntryLine"]] = relationship(
        back_populates="entry", lazy="select", cascade="all, delete-orphan"
    )


class JournalEntryLine(BaseModel):
    """Debit or credit line inside a journal entry."""

    __tablename__ = "journal_entry_line"
    __table_args__ = ({"schema": "accounting"},)

    entry_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounting.journal_entry.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="RESTRICT"), nullable=False
    )
    debit: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    credit: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    currency: Mapped[str] = mapped_column(String(10), default="THB")
    memo: Mapped[str | None] = mapped_column(String(240))
    partner_type: Mapped[str | None] = mapped_column(String(20))
    partner_id: Mapped[int | None] = mapped_column(BigInteger)
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)

    entry: Mapped[JournalEntry] = relationship(back_populates="lines", lazy="select")
    account: Mapped[Account] = relationship(lazy="select")


class TaxRate(BaseModel):
    """Tax rate definition (VAT, WHT, etc.)."""

    __tablename__ = "tax_rate"
    __table_args__ = ({"schema": "accounting"},)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rate_pct: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    tax_type: Mapped[str] = mapped_column(String(20), default="vat")
    account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

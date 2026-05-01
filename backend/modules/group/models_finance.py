"""Group-wide cash management — bank accounts, cash pool, daily forecast.

Most ERPs expose bank reconciliation per legal entity.  Treasurers in
small-group setups end up exporting balances daily into spreadsheets to
see the consolidated cash position.  These models give a single
authoritative view across companies.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
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


BANK_ACCOUNT_TYPES = ("checking", "savings", "fixed", "credit_line", "petty_cash")


class BankAccount(BaseModel):
    """One bank account belonging to one operating company.

    Balances are tracked per account; consolidated views aggregate across
    members of a CashPool.
    """

    __tablename__ = "bank_account"
    __table_args__ = (
        UniqueConstraint("company_id", "account_number", name="uq_bank_account"),
        {"schema": "grp"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_number: Mapped[str] = mapped_column(String(40), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), default="checking", nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    current_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    available_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CashPool(BaseModel):
    """A treasury aggregation — many bank accounts, one consolidated view.

    Pools have a target balance; members are bank accounts.  The pool
    engine suggests sweeps (transfers) to keep total balance at target
    while minimising idle cash in low-yield accounts.
    """

    __tablename__ = "cash_pool"
    __table_args__ = ({"schema": "grp"},)

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="CASCADE"), nullable=False
    )
    target_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    sweep_threshold_pct: Mapped[float] = mapped_column(Float, default=20, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["CashPoolMember"]] = relationship(
        back_populates="pool",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CashPoolMember(BaseModel):
    __tablename__ = "cash_pool_member"
    __table_args__ = (
        UniqueConstraint("pool_id", "bank_account_id", name="uq_cash_pool_member"),
        {"schema": "grp"},
    )

    pool_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.cash_pool.id", ondelete="CASCADE"), nullable=False
    )
    bank_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.bank_account.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    min_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)

    pool: Mapped[CashPool] = relationship(back_populates="members", lazy="select")


class CashForecastSnapshot(BaseModel):
    """Daily group-wide cash forecast — append-only.

    The forecast job runs once per day and writes a snapshot per company
    + horizon.  ``projected_balance = current_balance + sum(cash_in) -
    sum(cash_out)`` over the horizon.  ``breakdown`` lists upcoming AR
    receipts + AP payments contributing to the forecast.
    """

    __tablename__ = "cash_forecast_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "forecast_date", "horizon_days", name="uq_cash_forecast"
        ),
        {"schema": "grp"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    opening_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    cash_in: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    cash_out: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    projected_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    risk_flag: Mapped[str] = mapped_column(String(20), default="ok", nullable=False)
    breakdown: Mapped[dict | None] = mapped_column(JSON, default=None)


class GroupAccrual(BaseModel):
    """Multi-company expense / liability accrued evenly over time.

    E.g. an annual insurance premium of 1.2M THB paid up-front is accrued
    as 100k/month split across companies by an `ALLOCATION_BASIS` rule.
    Once posted to journal entries, leftover liability is tracked here so
    drawdown / cancellation is auditable.
    """

    __tablename__ = "group_accrual"
    __table_args__ = ({"schema": "grp"},)

    ref: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    paying_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    accrual_basis: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    accrued_to_date: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    state: Mapped[str] = mapped_column(String(15), default="active", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

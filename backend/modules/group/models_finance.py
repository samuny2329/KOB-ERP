"""Group module finance models — treasury, loans, transfer pricing, cost allocation."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


class BankAccount(BaseModel):
    """Corporate bank account per company."""

    __tablename__ = "bank_account"
    __table_args__ = ({"schema": "grp"},)

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_no: Mapped[str] = mapped_column(String(60), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), default="current", nullable=False)  # current/savings/fx
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CashPool(BaseModel):
    """Notional cash pooling header — sweeps balances across accounts."""

    __tablename__ = "cash_pool"
    __table_args__ = ({"schema": "grp"},)

    pool_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    lead_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    target_balance: Mapped[float] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    sweep_threshold: Mapped[float] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["CashPoolMember"]] = relationship(
        back_populates="pool", lazy="select", cascade="all, delete-orphan"
    )


class CashPoolMember(BaseModel):
    """Bank account participation in a cash pool."""

    __tablename__ = "cash_pool_member"
    __table_args__ = (
        UniqueConstraint("pool_id", "bank_account_id", name="uq_cash_pool_member"),
        {"schema": "grp"},
    )

    pool_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.cash_pool.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.bank_account.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False
    )

    pool: Mapped[CashPool] = relationship(back_populates="members", lazy="select")


class CashForecastSnapshot(BaseModel):
    """Daily cash forecast snapshot per company — used for risk classification."""

    __tablename__ = "cash_forecast_snapshot"
    __table_args__ = (
        UniqueConstraint("company_id", "forecast_date", name="uq_cash_forecast_company_date"),
        {"schema": "grp"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    opening: Mapped[float] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    projected_in: Mapped[float] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    projected_out: Mapped[float] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    closing: Mapped[float] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    risk_flag: Mapped[str] = mapped_column(String(10), default="ok", nullable=False)  # ok/low/critical


class IntercompanyLoan(BaseModel):
    """Intercompany loan between two group entities."""

    __tablename__ = "intercompany_loan"
    __table_args__ = ({"schema": "grp"},)

    lender_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    borrower_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    principal: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    interest_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    outstanding: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    next_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    installments: Mapped[list["IntercompanyLoanInstallment"]] = relationship(
        back_populates="loan", lazy="select", cascade="all, delete-orphan"
    )


class IntercompanyLoanInstallment(BaseModel):
    """Scheduled installment for an intercompany loan."""

    __tablename__ = "intercompany_loan_installment"
    __table_args__ = ({"schema": "grp"},)

    loan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.intercompany_loan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    principal_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    interest_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    loan: Mapped[IntercompanyLoan] = relationship(back_populates="installments", lazy="select")


class TransferPriceRule(BaseModel):
    """Transfer pricing rule for IC transactions (TNMM, cost-plus, etc.)."""

    __tablename__ = "transfer_price_rule"
    __table_args__ = ({"schema": "grp"},)

    from_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    to_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    product_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    method: Mapped[str] = mapped_column(String(20), default="cost_plus", nullable=False)
    markup_pct: Mapped[float] = mapped_column(Numeric(6, 3), default=0, nullable=False)
    documentation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CrossCompanyCostAllocation(BaseModel, WorkflowMixin):
    """Cross-company cost allocation header — split shared costs across subsidiaries."""

    __tablename__ = "cross_company_cost_allocation"
    __table_args__ = ({"schema": "grp"},)

    allowed_transitions: dict = {
        "draft": {"validated", "cancelled"},
        "validated": set(),
        "cancelled": set(),
    }

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    basis: Mapped[str] = mapped_column(String(40), nullable=False)  # revenue/headcount/floor_area/equal
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. 2025-04
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["CostAllocationLine"]] = relationship(
        back_populates="allocation", lazy="select", cascade="all, delete-orphan"
    )


class CostAllocationLine(BaseModel):
    """Per-company share line in a cost allocation."""

    __tablename__ = "cost_allocation_line"
    __table_args__ = ({"schema": "grp"},)

    allocation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.cross_company_cost_allocation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False
    )
    share_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    basis_value: Mapped[float] = mapped_column(Numeric(20, 4), default=0, nullable=False)

    allocation: Mapped[CrossCompanyCostAllocation] = relationship(back_populates="lines", lazy="select")


class GroupAccrual(BaseModel):
    """Group-level accrual entry — shortfall provision across companies."""

    __tablename__ = "group_accrual"
    __table_args__ = ({"schema": "grp"},)

    description: Mapped[str] = mapped_column(String(240), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)

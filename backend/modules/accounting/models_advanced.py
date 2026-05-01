"""Accounting advanced — Thai compliance + multi-company financial models.

  * VAT (ภพ.30) monthly preparation w/ input/output line capture
  * WHT certificate issuance (ภงด.3 / ภงด.53)
  * Fixed asset register + depreciation schedule (straight-line / declining)
  * FX revaluation snapshot per period (multi-currency)

All carry ``company_id`` so multi-company P&L / Balance Sheet works.
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
from backend.core.workflow import WorkflowMixin


# ── VAT (ภพ.30 monthly) ────────────────────────────────────────────────


class VatPeriod(BaseModel, WorkflowMixin):
    """Monthly VAT period header per company.

    Aggregates ``vat_line`` rows from sales (output VAT) and purchase
    (input VAT) for the month.  ``net_payable = output_vat - input_vat``.
    Negative net = refund/credit carried forward.

    State machine:
      draft → calculated → submitted → settled  (terminal)
                                     ↘ amended    (re-open & re-submit)
              ↓
        cancelled  (terminal — voided period)
    """

    __tablename__ = "vat_period"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "period_year", "period_month", name="uq_vat_period"
        ),
        {"schema": "accounting"},
    )

    initial_state = "draft"
    allowed_transitions = {
        "draft": {"calculated", "cancelled"},
        "calculated": {"submitted", "draft", "cancelled"},
        "submitted": {"settled", "amended"},
        "amended": {"calculated"},
        "settled": set(),
        "cancelled": set(),
    }

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    output_vat: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    input_vat: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    net_payable: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    credit_carried_forward: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    rd_receipt_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["VatLine"]] = relationship(
        back_populates="period", lazy="selectin", cascade="all, delete-orphan"
    )


# Direction: input = VAT KOB pays on purchases (claimable);
# output = VAT KOB charges customers (payable).
VAT_DIRECTIONS = ("input", "output")


class VatLine(BaseModel):
    """Per-document VAT line in a VAT period.

    Source can be a ``sales.sales_order`` (output) or a ``purchase.purchase_order``
    (input).  ``source_model`` and ``source_id`` provide an audit trail
    back to the originating document.
    """

    __tablename__ = "vat_line"
    __table_args__ = ({"schema": "accounting"},)

    period_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounting.vat_period.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    counterparty_name: Mapped[str] = mapped_column(String(255), nullable=False)
    counterparty_tax_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    base_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    vat_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    source_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    period: Mapped[VatPeriod] = relationship(back_populates="lines", lazy="select")


# ── WHT certificate (ภงด.3 / ภงด.53) ───────────────────────────────────


WHT_FORM_TYPES = ("pnd3", "pnd53", "pnd2", "pnd1a")


class WhtCertificate(BaseModel):
    """A WHT certificate issued by the company to a payee.

    Required to be given to the supplier when KOB withholds tax (e.g.
    professional services 3%, rent 5%, advertising 2%).  Tax authority
    certificates are sequentially numbered per company per year.
    """

    __tablename__ = "wht_certificate"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "form_type", "period_year", "sequence_number",
            name="uq_wht_cert_seq",
        ),
        {"schema": "accounting"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    form_type: Mapped[str] = mapped_column(String(10), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    payee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payee_tax_id: Mapped[str] = mapped_column(String(40), nullable=False)
    payee_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    income_type_code: Mapped[str] = mapped_column(String(10), nullable=False)
    income_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    wht_rate_pct: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    wht_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    journal_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.journal_entry.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── Fixed asset register ───────────────────────────────────────────────


DEPRECIATION_METHODS = ("straight_line", "declining_balance", "units_of_production")


class FixedAsset(BaseModel, WorkflowMixin):
    """Depreciable asset.

    State machine:
      pending → in_use → fully_depreciated   (terminal)
                       ↘ disposed              (terminal)
            ↓
      cancelled (from pending only)

    ``salvage_value`` reduces the depreciable base.  ``useful_life_months``
    drives the schedule (12 = 1yr, 60 = 5yr, etc).
    """

    __tablename__ = "fixed_asset"
    __table_args__ = ({"schema": "accounting"},)

    initial_state = "pending"
    allowed_transitions = {
        "pending": {"in_use", "cancelled"},
        "in_use": {"fully_depreciated", "disposed"},
        "fully_depreciated": set(),
        "disposed": set(),
        "cancelled": set(),
    }

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    asset_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False)
    acquisition_cost: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    salvage_value: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    depreciation_method: Mapped[str] = mapped_column(
        String(30), default="straight_line", nullable=False
    )
    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False)
    accumulated_depreciation: Mapped[float] = mapped_column(
        Numeric(16, 2), default=0, nullable=False
    )
    book_value: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    asset_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )
    accumulated_depreciation_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )
    depreciation_expense_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    custodian_employee_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("hr.employee.id", ondelete="SET NULL"), nullable=True
    )
    disposal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_proceeds: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    schedule: Mapped[list["DepreciationEntry"]] = relationship(
        back_populates="asset", lazy="selectin", cascade="all, delete-orphan"
    )


class DepreciationEntry(BaseModel):
    """One scheduled depreciation row for a fixed asset."""

    __tablename__ = "depreciation_entry"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "period_year", "period_month", name="uq_dep_entry_period"
        ),
        {"schema": "accounting"},
    )

    asset_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounting.fixed_asset.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    depreciation_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    accumulated_to_date: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    book_value_after: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    journal_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.journal_entry.id", ondelete="SET NULL"), nullable=True
    )

    asset: Mapped[FixedAsset] = relationship(back_populates="schedule", lazy="select")


# ── FX revaluation ─────────────────────────────────────────────────────


class FxRevaluation(BaseModel):
    """Period-end FX revaluation snapshot per (company, currency).

    Translates monetary balances at period-end rate vs the booked rate;
    the difference is FX gain/loss recognised in the same period.
    """

    __tablename__ = "fx_revaluation"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "currency", "period_year", "period_month",
            name="uq_fx_revaluation",
        ),
        {"schema": "accounting"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_end_rate: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False)
    booked_balance_fc: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    booked_balance_thb: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    revalued_balance_thb: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    fx_gain_loss: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    journal_entry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.journal_entry.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

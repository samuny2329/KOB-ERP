"""Group / multi-company models.

All models reference ``core.company``.  Most carry a ``period_start`` /
``period_end`` window so historical snapshots stay queryable.
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


# ── Group-wide KPI rollup ──────────────────────────────────────────────


KPI_METRICS = (
    "revenue",
    "gross_margin",
    "fulfillment_sla_pct",
    "pick_accuracy_pct",
    "ar_days",
    "ap_days",
    "headcount",
    "active_customers",
)


class GroupKpiSnapshot(BaseModel):
    """Aggregate KPI for one company over a window.

    The "group" view is just a sum/avg query across siblings — we don't
    persist a separate parent row.  Instead the rollup endpoint walks the
    company hierarchy and aggregates these snapshots on the fly.

    Why not a view? we want point-in-time history (snapshots are immutable).
    """

    __tablename__ = "group_kpi_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "metric", "period_start", name="uq_group_kpi_window"
        ),
        {"schema": "grp"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    breakdown: Mapped[dict | None] = mapped_column(JSON, default=None)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.utcnow()
    )


# ── Inventory pooling across companies ─────────────────────────────────


class InventoryPool(BaseModel):
    """Virtual stock pool spanning multiple companies' warehouses.

    Members of a pool share their ``wms.warehouse`` rows; routing rules
    decide which member to fulfill from based on availability, distance,
    or transfer-pricing cost.
    """

    __tablename__ = "inventory_pool"
    __table_args__ = ({"schema": "grp"},)

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="CASCADE"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["InventoryPoolMember"]] = relationship(
        back_populates="pool", lazy="selectin", cascade="all, delete-orphan"
    )
    rules: Mapped[list["InventoryPoolRule"]] = relationship(
        back_populates="pool", lazy="selectin", cascade="all, delete-orphan"
    )


class InventoryPoolMember(BaseModel):
    """A warehouse + the company it belongs to participating in a pool."""

    __tablename__ = "inventory_pool_member"
    __table_args__ = (
        UniqueConstraint("pool_id", "warehouse_id", name="uq_pool_member"),
        {"schema": "grp"},
    )

    pool_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.inventory_pool.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wms.warehouse.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    transfer_cost_per_km: Mapped[float] = mapped_column(Numeric(10, 4), default=0)

    pool: Mapped[InventoryPool] = relationship(back_populates="members", lazy="select")


# How the routing engine ranks members for a given demand.
ROUTING_STRATEGIES = ("priority", "lowest_cost", "nearest", "balance_load")


class InventoryPoolRule(BaseModel):
    """Per-pool routing strategy + product/category overrides."""

    __tablename__ = "inventory_pool_rule"
    __table_args__ = ({"schema": "grp"},)

    pool_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.inventory_pool.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    product_category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wms.product_category.id", ondelete="CASCADE"), nullable=True
    )
    strategy: Mapped[str] = mapped_column(String(20), default="priority", nullable=False)
    min_qty_threshold: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    pool: Mapped[InventoryPool] = relationship(back_populates="rules", lazy="select")


# ── Cross-company cost allocation ──────────────────────────────────────


ALLOCATION_BASIS = ("revenue_pct", "headcount_pct", "fixed", "sqm_pct", "manual")


class CostAllocation(BaseModel, WorkflowMixin):
    """Shared expense pool — split across companies by configurable basis.

    State flow:
      draft → calculated → posted   (terminal)
                       ↘ cancelled  (terminal)

    Once posted, downstream accounting picks up the split via
    ``source_model='grp.cost_allocation'`` on JournalEntry.
    """

    __tablename__ = "cost_allocation"
    __table_args__ = ({"schema": "grp"},)

    initial_state = "draft"
    allowed_transitions = {
        "draft": {"calculated", "cancelled"},
        "calculated": {"posted", "draft", "cancelled"},
        "posted": set(),
        "cancelled": set(),
    }

    ref: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    paying_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    basis: Mapped[str] = mapped_column(String(20), nullable=False)
    expense_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounting.account.id", ondelete="SET NULL"), nullable=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    rules: Mapped[list["CostAllocationLine"]] = relationship(
        back_populates="allocation", lazy="selectin", cascade="all, delete-orphan"
    )


class CostAllocationLine(BaseModel):
    """Per-company portion of a CostAllocation.

    ``share_pct`` is computed when allocation moves to ``calculated``.
    ``amount`` = total_amount × share_pct / 100.
    """

    __tablename__ = "cost_allocation_line"
    __table_args__ = (
        UniqueConstraint(
            "allocation_id", "company_id", name="uq_alloc_company"
        ),
        {"schema": "grp"},
    )

    allocation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.cost_allocation.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    share_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    allocation: Mapped[CostAllocation] = relationship(back_populates="rules", lazy="select")


# ── Inter-company loans ────────────────────────────────────────────────


class InterCompanyLoan(BaseModel, WorkflowMixin):
    """When company A pays company B's bill (or lends cash), record as loan.

    Tracks principal + interest schedule + outstanding balance.  Closes
    when fully repaid (state ``settled``).

    State flow:
      draft → active → settled   (terminal)
                   ↘ defaulted   (terminal — long overdue)
              ↘ cancelled       (from draft only)
    """

    __tablename__ = "intercompany_loan"
    __table_args__ = ({"schema": "grp"},)

    initial_state = "draft"
    allowed_transitions = {
        "draft": {"active", "cancelled"},
        "active": {"settled", "defaulted"},
        "settled": set(),
        "defaulted": set(),
        "cancelled": set(),
    }

    ref: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    lender_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    borrower_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    principal: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    interest_rate_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    settled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    outstanding_balance: Mapped[float] = mapped_column(
        Numeric(16, 2), default=0, nullable=False
    )
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)

    installments: Mapped[list["LoanInstallment"]] = relationship(
        back_populates="loan", lazy="selectin", cascade="all, delete-orphan"
    )


class LoanInstallment(BaseModel):
    """Scheduled repayment for an InterCompanyLoan."""

    __tablename__ = "loan_installment"
    __table_args__ = ({"schema": "grp"},)

    loan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.intercompany_loan.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    principal_due: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    interest_due: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    state: Mapped[str] = mapped_column(String(15), default="pending", nullable=False)

    loan: Mapped[InterCompanyLoan] = relationship(back_populates="installments", lazy="select")


# ── Thai tax-group (VAT consolidation) ─────────────────────────────────


class TaxGroup(BaseModel):
    """A registered VAT group (Thai: กลุ่มภาษีมูลค่าเพิ่ม).

    Member companies file a single consolidated VAT return.  Inter-member
    transactions are excluded from external taxable supplies.
    """

    __tablename__ = "tax_group"
    __table_args__ = ({"schema": "grp"},)

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    representative_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="RESTRICT"), nullable=False
    )
    tax_authority_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["TaxGroupMember"]] = relationship(
        back_populates="tax_group", lazy="selectin", cascade="all, delete-orphan"
    )


class TaxGroupMember(BaseModel):
    __tablename__ = "tax_group_member"
    __table_args__ = (
        UniqueConstraint("tax_group_id", "company_id", name="uq_tax_group_member"),
        {"schema": "grp"},
    )

    tax_group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.tax_group.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="CASCADE"), nullable=False
    )
    joined_date: Mapped[date] = mapped_column(Date, nullable=False)
    left_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    tax_group: Mapped[TaxGroup] = relationship(back_populates="members", lazy="select")


# ── Per-company approval matrix ────────────────────────────────────────


APPROVABLE_DOCS = (
    "purchase_order",
    "sales_order",
    "journal_entry",
    "leave",
    "payslip",
    "cost_allocation",
    "intercompany_loan",
)


class ApprovalMatrix(BaseModel):
    """Defines how documents in a given company travel through approvals."""

    __tablename__ = "approval_matrix"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "document_type", name="uq_approval_matrix_doc"
        ),
        {"schema": "grp"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rules: Mapped[list["ApprovalMatrixRule"]] = relationship(
        back_populates="matrix", lazy="selectin", cascade="all, delete-orphan"
    )


class ApprovalMatrixRule(BaseModel):
    """One threshold rule in an approval matrix.

    Multiple rules per matrix are evaluated in ``sequence`` order; the
    first whose ``min_amount <= doc.total < max_amount (or no max)``
    matches.  ``approver_user_id`` and/or ``approver_group_id`` decide who
    must sign off.
    """

    __tablename__ = "approval_matrix_rule"
    __table_args__ = ({"schema": "grp"},)

    matrix_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.approval_matrix.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    min_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    max_amount: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    approver_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    approver_group_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.group.id", ondelete="SET NULL"), nullable=True
    )
    requires_n_approvers: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    matrix: Mapped[ApprovalMatrix] = relationship(back_populates="rules", lazy="select")


# ── Compliance calendar (Thai SME) ─────────────────────────────────────


COMPLIANCE_TYPES = (
    "vat_pp30",          # ภพ.30 monthly VAT return
    "wht_pnd1",          # ภงด.1 monthly WHT for employees
    "wht_pnd3",          # ภงด.3 monthly WHT (individuals)
    "wht_pnd53",         # ภงด.53 monthly WHT (companies)
    "social_security",   # SSO monthly contribution
    "annual_audit",      # year-end audit submission
    "corporate_pnd50",   # ภงด.50 annual CIT return
    "half_year_pnd51",   # ภงด.51 mid-year CIT return
    "trademark_renewal",
    "license_renewal",
    "other",
)


class CompanyComplianceItem(BaseModel, WorkflowMixin):
    """A regulatory deadline tied to a single company.

    State flow:
      pending → in_progress → submitted   (terminal)
                          ↘ overdue       (auto-set when due_date passes)
              ↘ cancelled                  (terminal)
    """

    __tablename__ = "compliance_item"
    __table_args__ = ({"schema": "grp"},)

    initial_state = "pending"
    allowed_transitions = {
        "pending": {"in_progress", "overdue", "cancelled"},
        "in_progress": {"submitted", "overdue"},
        "submitted": set(),
        "overdue": {"in_progress", "submitted"},
        "cancelled": set(),
    }

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    compliance_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    period_label: Mapped[str] = mapped_column(String(40), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    submitted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    submitted_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
    reference_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount_filed: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

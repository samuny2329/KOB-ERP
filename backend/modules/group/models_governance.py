"""Group module governance models — compliance, approvals, brand licenses, Thai tax."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.base_model import BaseModel
from backend.core.workflow import WorkflowMixin


THAI_FILING_TYPES = (
    "pp30",      # ภพ.30 — monthly VAT
    "pnd1",      # ภงด.1 — monthly employee WHT
    "pnd3",      # ภงด.3 — individual vendor WHT
    "pnd53",     # ภงด.53 — corporate vendor WHT
    "sso",       # Social Security Office filing
    "pnd50",     # ภงด.50 — annual corporate tax return
    "pnd51",     # ภงด.51 — semi-annual corporate tax
    "audit",     # Annual statutory audit filing
    "license",   # Business license renewal
)


class ThaiTaxGroup(BaseModel):
    """Thai tax treatment settings for a company group."""

    __tablename__ = "thai_tax_group"
    __table_args__ = (
        UniqueConstraint("group_id", name="uq_thai_tax_group"),
        {"schema": "grp"},
    )

    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company_group.id", ondelete="CASCADE"), nullable=False
    )
    flag_ic_vat_exempt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    threshold_ownership_pct: Mapped[float] = mapped_column(Numeric(6, 3), default=25.0, nullable=False)


class CompanyApprovalMatrix(BaseModel):
    """Approval threshold rule per document type per company."""

    __tablename__ = "company_approval_matrix"
    __table_args__ = (
        UniqueConstraint("company_id", "document_type", "amount_threshold", name="uq_approval_matrix"),
        {"schema": "grp"},
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)  # purchase_order/sales_order/payment/etc
    amount_threshold: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    approver_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="RESTRICT"), nullable=False
    )
    min_approvers: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ApprovalSubstitution(BaseModel):
    """Temporary approver substitution (e.g. during leave)."""

    __tablename__ = "approval_substitution"
    __table_args__ = ({"schema": "grp"},)

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approver_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="CASCADE"), nullable=False
    )
    substitute_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.user.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str | None] = mapped_column(String(40), nullable=True)  # None = all document types
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)


class ComplianceCalendar(BaseModel, WorkflowMixin):
    """Thai statutory filing tracker — deadline monitoring with state machine."""

    __tablename__ = "compliance_calendar"
    __table_args__ = (
        UniqueConstraint("company_id", "filing_type", "period_year", "period_month", name="uq_compliance_filing"),
        {"schema": "grp"},
    )

    allowed_transitions: dict = {
        "pending": {"submitted", "overdue"},
        "submitted": {"accepted"},
        "overdue": {"recovered"},
        "accepted": set(),
        "recovered": set(),
    }

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filing_type: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ref_number: Mapped[str | None] = mapped_column(String(80), nullable=True)


class BrandLicense(BaseModel):
    """Brand license agreement between group companies."""

    __tablename__ = "brand_license"
    __table_args__ = ({"schema": "grp"},)

    owner_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    licensee_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grp.company.id", ondelete="RESTRICT"), nullable=False
    )
    brand_name: Mapped[str] = mapped_column(String(120), nullable=False)
    territory: Mapped[str | None] = mapped_column(String(80), nullable=True)
    royalty_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    license_scope: Mapped[str] = mapped_column(String(20), default="non_exclusive", nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

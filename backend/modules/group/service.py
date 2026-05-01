"""Group / multi-company business logic.

These functions are intentionally pure where possible — heavy
computations (KPI rollup, allocation maths, routing pick) operate on
in-memory snapshots so they're easy to test without a Postgres in
the loop.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.models import Company
from backend.core.workflow import WorkflowError
from backend.modules.group.models import (
    ApprovalMatrix,
    ApprovalMatrixRule,
    CostAllocation,
    CostAllocationLine,
    GroupKpiSnapshot,
    InterCompanyLoan,
    InventoryPool,
    InventoryPoolMember,
    LoanInstallment,
    TaxGroup,
)
from backend.modules.inventory.models import StockQuant
from backend.modules.wms.models import Warehouse


# ── Group KPI rollup ───────────────────────────────────────────────────


async def rollup_kpi(
    session: AsyncSession,
    parent_company_id: int,
    metric: str,
    period_start: date,
    period_end: date,
) -> dict:
    """Sum KPI snapshots across the parent + its direct subsidiaries.

    Doesn't recurse infinitely — only one generation deep (parent + direct
    children).  Going deeper is rare in Thai SMEs and easy to add later.
    """
    parent = await session.get(Company, parent_company_id)
    if parent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "parent company not found")

    # Pull the parent's own snapshot for this metric/window
    own_stmt = select(GroupKpiSnapshot).where(
        GroupKpiSnapshot.company_id == parent_company_id,
        GroupKpiSnapshot.metric == metric,
        GroupKpiSnapshot.period_start == period_start,
        GroupKpiSnapshot.period_end == period_end,
    )
    own = (await session.execute(own_stmt)).scalar_one_or_none()
    own_value = float(own.value) if own else 0.0

    # Children
    children_stmt = select(Company).where(Company.parent_id == parent_company_id)
    children = (await session.execute(children_stmt)).scalars().all()

    children_breakdown = []
    children_total = 0.0
    for child in children:
        snap_stmt = select(GroupKpiSnapshot).where(
            GroupKpiSnapshot.company_id == child.id,
            GroupKpiSnapshot.metric == metric,
            GroupKpiSnapshot.period_start == period_start,
            GroupKpiSnapshot.period_end == period_end,
        )
        snap = (await session.execute(snap_stmt)).scalar_one_or_none()
        value = float(snap.value) if snap else 0.0
        children_breakdown.append(
            {"company_id": child.id, "code": child.code, "name": child.name, "value": value}
        )
        children_total += value

    return {
        "parent_company_id": parent_company_id,
        "metric": metric,
        "period_start": period_start,
        "period_end": period_end,
        "own_value": own_value,
        "children_value": children_total,
        "total_value": own_value + children_total,
        "children_breakdown": children_breakdown,
    }


# ── Inventory pool routing ─────────────────────────────────────────────


def rank_pool_options(
    members: list[dict],
    qty_required: float,
    strategy: str = "priority",
) -> list[dict]:
    """Pure-function ranker — order pool members by routing strategy.

    ``members`` is a list of dicts with keys:
      ``company_id, warehouse_id, available_qty, priority, transfer_cost_per_km``

    Returns the same list with an extra ``estimated_cost`` and ``chosen``
    field, sorted best-first.  Members lacking enough stock are dropped
    unless every option is short, in which case we keep them so the API
    can still return a response.
    """
    enriched = []
    for m in members:
        avail = float(m.get("available_qty", 0))
        if avail >= qty_required:
            short = False
        else:
            short = True
        enriched.append({**m, "short": short})

    if strategy == "priority":
        enriched.sort(key=lambda m: (m["short"], m["priority"]))
    elif strategy == "lowest_cost":
        for m in enriched:
            m["estimated_cost"] = float(m.get("transfer_cost_per_km", 0)) * qty_required
        enriched.sort(key=lambda m: (m["short"], m["estimated_cost"]))
    elif strategy == "balance_load":
        enriched.sort(key=lambda m: (m["short"], -float(m.get("available_qty", 0))))
    else:  # nearest — same as lowest_cost in v1 (no postal data yet)
        enriched.sort(key=lambda m: (m["short"], float(m.get("transfer_cost_per_km", 0))))

    if enriched:
        enriched[0]["chosen"] = True
        for m in enriched[1:]:
            m["chosen"] = False
    for m in enriched:
        m.setdefault("estimated_cost", 0.0)
    return enriched


async def lookup_pool_stock(
    session: AsyncSession,
    pool_id: int,
    product_id: int,
    qty: float,
) -> list[dict]:
    """Find which member of a pool can satisfy ``qty`` of ``product_id``.

    Walks every InventoryPoolMember, joins to StockQuant for the warehouse,
    sums available qty, then ranks via the active rule's strategy.
    """
    pool_stmt = (
        select(InventoryPool)
        .where(InventoryPool.id == pool_id, InventoryPool.deleted_at.is_(None))
        .options(selectinload(InventoryPool.members), selectinload(InventoryPool.rules))
    )
    pool = (await session.execute(pool_stmt)).scalar_one_or_none()
    if pool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "inventory pool not found")

    members_in: list[dict] = []
    for m in pool.members:
        # Sum stock_quant for (product_id, internal locations of the warehouse)
        # Simplified: use sum of all quants where Location.warehouse_id matches.
        from sqlalchemy import func
        from backend.modules.wms.models import Location

        qty_stmt = (
            select(func.coalesce(func.sum(StockQuant.quantity - StockQuant.reserved_quantity), 0))
            .join(Location, Location.id == StockQuant.location_id)
            .where(
                Location.warehouse_id == m.warehouse_id,
                Location.usage == "internal",
                StockQuant.product_id == product_id,
            )
        )
        avail = float((await session.execute(qty_stmt)).scalar() or 0)
        members_in.append({
            "company_id": m.company_id,
            "warehouse_id": m.warehouse_id,
            "available_qty": avail,
            "priority": m.priority,
            "transfer_cost_per_km": float(m.transfer_cost_per_km),
        })

    strategy = pool.rules[0].strategy if pool.rules else "priority"
    return rank_pool_options(members_in, qty, strategy)


# ── Cost allocation maths ──────────────────────────────────────────────


def compute_allocation_shares(
    total: float,
    members: list[dict],
    basis: str,
) -> list[dict]:
    """Pure-function: split ``total`` across ``members`` by ``basis``.

    ``members`` is a list of dicts with keys:
      - company_id (always)
      - revenue (for revenue_pct)
      - headcount (for headcount_pct)
      - sqm (for sqm_pct)
      - manual_share_pct (for manual)
      - manual_amount (for fixed)

    Returns each member with ``share_pct`` and ``amount`` populated.
    """
    out = []
    if basis == "fixed":
        for m in members:
            amt = float(m.get("manual_amount", 0))
            out.append({
                **m,
                "amount": amt,
                "share_pct": (amt / total * 100) if total > 0 else 0,
            })
        return out

    if basis == "manual":
        for m in members:
            pct = float(m.get("manual_share_pct", 0))
            out.append({
                **m,
                "share_pct": pct,
                "amount": round(total * pct / 100, 2),
            })
        return out

    key = {"revenue_pct": "revenue", "headcount_pct": "headcount", "sqm_pct": "sqm"}.get(basis)
    if key is None:
        raise ValueError(f"unknown basis: {basis!r}")

    grand = sum(float(m.get(key, 0)) for m in members)
    if grand <= 0:
        raise ValueError(f"sum of {key!r} across members must be > 0 to allocate")

    for m in members:
        weight = float(m.get(key, 0))
        pct = weight / grand * 100
        out.append({
            **m,
            "share_pct": round(pct, 4),
            "amount": round(total * pct / 100, 2),
        })
    return out


async def calculate_allocation(
    session: AsyncSession, allocation: CostAllocation
) -> CostAllocation:
    """Move CostAllocation from draft → calculated.

    Validates that the line list adds to ~100% (within 0.01%) for percent-
    based bases, or that fixed amounts add up to total.
    """
    try:
        allocation.transition("calculated")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    total_pct = sum(float(line.share_pct) for line in allocation.rules)
    total_amount = sum(float(line.amount) for line in allocation.rules)

    if allocation.basis == "fixed":
        if abs(total_amount - float(allocation.total_amount)) > 0.01:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"sum of fixed amounts ({total_amount}) != allocation total ({allocation.total_amount})",
            )
    else:
        if abs(total_pct - 100.0) > 0.01:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"sum of share_pct ({total_pct}%) must equal 100%",
            )
    return allocation


async def post_allocation(
    session: AsyncSession, allocation: CostAllocation
) -> CostAllocation:
    """calculated → posted.  In production this also creates JE entries."""
    try:
        allocation.transition("posted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    allocation.posted_at = datetime.now(UTC)
    return allocation


# ── Inter-company loans ────────────────────────────────────────────────


async def activate_loan(
    session: AsyncSession, loan: InterCompanyLoan
) -> InterCompanyLoan:
    """draft → active.  Sets outstanding_balance = principal."""
    try:
        loan.transition("active")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    loan.outstanding_balance = loan.principal
    return loan


async def repay_installment(
    session: AsyncSession,
    loan: InterCompanyLoan,
    installment_id: int,
    paid_amount: float,
    paid_date: date,
) -> InstalledLoanResult:  # type: ignore[name-defined]
    """Apply a payment to a loan installment, update balances, possibly settle.

    Returns the updated installment.  If the loan's outstanding balance
    falls to zero, transitions the loan to ``settled``.
    """
    if loan.state != "active":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"loan must be 'active' to receive payments (current: {loan.state})",
        )
    target = next((i for i in loan.installments if i.id == installment_id), None)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "installment not found")

    target.paid_amount = float(target.paid_amount) + float(paid_amount)
    target.paid_date = paid_date

    # Update state of installment + loan
    due = float(target.principal_due) + float(target.interest_due)
    if abs(target.paid_amount - due) < 0.01:
        target.state = "paid"
    elif target.paid_amount > due:
        target.state = "overpaid"
    else:
        target.state = "partial"

    # Recompute loan outstanding balance
    paid_principal = sum(
        min(float(i.paid_amount), float(i.principal_due)) for i in loan.installments
    )
    loan.outstanding_balance = float(loan.principal) - paid_principal

    if loan.outstanding_balance <= 0.01:
        loan.outstanding_balance = 0
        try:
            loan.transition("settled")
            loan.settled_date = paid_date
        except WorkflowError:
            pass  # already terminal

    return target  # type: ignore[return-value]


# Keep mypy quiet on the forward reference above
InstalledLoanResult = LoanInstallment


# ── Approval matrix lookup ─────────────────────────────────────────────


async def lookup_approval(
    session: AsyncSession,
    company_id: int,
    document_type: str,
    amount: float,
) -> dict:
    """Find the matching approval rule for (company, doc, amount).

    Returns ``{matched, rule_id, approver_user_id, approver_group_id,
    requires_n_approvers}``.
    """
    matrix_stmt = (
        select(ApprovalMatrix)
        .where(
            ApprovalMatrix.company_id == company_id,
            ApprovalMatrix.document_type == document_type,
            ApprovalMatrix.active.is_(True),
            ApprovalMatrix.deleted_at.is_(None),
        )
        .options(selectinload(ApprovalMatrix.rules))
    )
    matrix = (await session.execute(matrix_stmt)).scalar_one_or_none()
    if matrix is None:
        return {
            "matched": False,
            "rule_id": None,
            "approver_user_id": None,
            "approver_group_id": None,
            "requires_n_approvers": 0,
        }

    for rule in sorted(matrix.rules, key=lambda r: r.sequence):
        if not rule.active:
            continue
        if amount < float(rule.min_amount):
            continue
        if rule.max_amount is not None and amount >= float(rule.max_amount):
            continue
        return {
            "matched": True,
            "rule_id": rule.id,
            "approver_user_id": rule.approver_user_id,
            "approver_group_id": rule.approver_group_id,
            "requires_n_approvers": rule.requires_n_approvers,
        }

    return {
        "matched": False,
        "rule_id": None,
        "approver_user_id": None,
        "approver_group_id": None,
        "requires_n_approvers": 0,
    }


# ── Tax group membership check ─────────────────────────────────────────


async def companies_in_same_tax_group(
    session: AsyncSession,
    company_a_id: int,
    company_b_id: int,
    on_date: date | None = None,
) -> bool:
    """True if both companies are members of the same active TaxGroup on
    ``on_date`` (default today).  Used by accounting to flag an inter-co
    sale as 'exempt from external VAT' when both parties are in one VAT
    group.
    """
    on_date = on_date or date.today()

    from backend.modules.group.models import TaxGroupMember

    stmt = (
        select(TaxGroupMember.tax_group_id)
        .where(
            TaxGroupMember.company_id.in_([company_a_id, company_b_id]),
            TaxGroupMember.joined_date <= on_date,
            or_(
                TaxGroupMember.left_date.is_(None),
                TaxGroupMember.left_date >= on_date,
            ),
        )
    )
    rows = (await session.execute(stmt)).all()
    if len(rows) < 2:
        return False
    groups = {r[0] for r in rows}
    # Both companies must share at least one common group
    a_groups = {r[0] for r in rows if r in rows}
    # Re-query per company to be precise
    stmt_a = stmt.where(TaxGroupMember.company_id == company_a_id)
    stmt_b = stmt.where(TaxGroupMember.company_id == company_b_id)
    a_set = {r[0] for r in (await session.execute(stmt_a)).all()}
    b_set = {r[0] for r in (await session.execute(stmt_b)).all()}
    return bool(a_set & b_set)

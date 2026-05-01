"""Group module business logic — pure functions + async DB operations."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.workflow import WorkflowError
from backend.modules.group.models import CompanyMembership, GroupKpiRollup
from backend.modules.group.models_finance import (
    CostAllocationLine,
    CrossCompanyCostAllocation,
    TransferPriceRule,
)
from backend.modules.group.models_governance import (
    ApprovalSubstitution,
    CompanyApprovalMatrix,
    ComplianceCalendar,
)
from backend.modules.group.models_partner import (
    VolumeRebateAccrual,
    VolumeRebateTier,
)


# ── Pure Functions (no DB) ─────────────────────────────────────────────


def compute_allocation_shares(
    lines_data: list[dict],
    basis: str,
) -> dict[int, float]:
    """Compute share_pct per company from basis values.

    lines_data: [{"company_id": int, "basis_value": float}, ...]
    Returns: {company_id: share_pct}
    """
    total = sum(d["basis_value"] for d in lines_data)
    if total == 0:
        n = len(lines_data)
        return {d["company_id"]: round(100 / n, 4) for d in lines_data} if n else {}
    return {
        d["company_id"]: round(d["basis_value"] / total * 100, 4)
        for d in lines_data
    }


def rank_pool_options(
    pool_members: list[dict],
    demand_qty: float,
    strategy: str,
) -> list[dict]:
    """Rank pool members by routing strategy.

    pool_members: [{"company_id", "priority", "available_qty", "unit_cost", "distance_km"}, ...]
    Returns sorted list with "rank" field appended.
    """
    if strategy == "priority":
        ranked = sorted(pool_members, key=lambda m: m.get("priority", 0))
    elif strategy == "lowest_cost":
        ranked = sorted(pool_members, key=lambda m: m.get("unit_cost", 0))
    elif strategy == "nearest":
        ranked = sorted(pool_members, key=lambda m: m.get("distance_km", 0))
    elif strategy == "balance_load":
        ranked = sorted(pool_members, key=lambda m: -m.get("available_qty", 0))
    else:
        ranked = list(pool_members)

    return [{**m, "rank": i + 1} for i, m in enumerate(ranked)]


def match_rebate_tier(
    tiers: list[dict],
    ytd_spend: float,
) -> dict | None:
    """Return the best-matching rebate tier for the given YTD spend."""
    eligible = [t for t in tiers if float(t["min_spend"]) <= ytd_spend]
    if not eligible:
        return None
    return max(eligible, key=lambda t: float(t["min_spend"]))


def classify_cash_risk(closing: float, target_balance: float) -> str:
    """Classify cash position risk level."""
    if target_balance <= 0:
        return "ok"
    ratio = closing / target_balance
    if ratio >= 0.5:
        return "ok"
    if ratio >= 0.2:
        return "low"
    return "critical"


def compute_group_kpi(
    company_tree: list[dict],
    metric_values: dict[int, float],
    aggregation: str = "sum",
) -> float:
    """Aggregate a metric across a company tree.

    company_tree: [{"company_id": int, "ownership_pct": float}, ...]
    metric_values: {company_id: float}
    aggregation: "sum" | "avg" | "last"
    """
    values = [metric_values.get(c["company_id"], 0.0) for c in company_tree]
    if not values:
        return 0.0
    if aggregation == "sum":
        return sum(values)
    if aggregation == "avg":
        return sum(values) / len(values)
    return values[-1]


# ── Async DB Operations ────────────────────────────────────────────────


async def rollup_kpi(
    session: AsyncSession,
    group_id: int,
    period: str,
    metric_name: str,
) -> list[GroupKpiRollup]:
    """Walk all companies in a group, aggregate metric, upsert rollup records."""
    memberships_result = await session.execute(
        select(CompanyMembership).where(CompanyMembership.group_id == group_id)
    )
    memberships = list(memberships_result.scalars().all())
    if not memberships:
        return []

    rollups = []
    for m in memberships:
        existing = (
            await session.execute(
                select(GroupKpiRollup).where(
                    GroupKpiRollup.company_id == m.company_id,
                    GroupKpiRollup.period == period,
                    GroupKpiRollup.metric_name == metric_name,
                )
            )
        ).scalar_one_or_none()

        if existing:
            rollups.append(existing)
        else:
            r = GroupKpiRollup(
                company_id=m.company_id,
                period=period,
                metric_name=metric_name,
                value=0.0,
                computed_at=datetime.now(UTC),
            )
            session.add(r)
            rollups.append(r)

    await session.flush()
    return rollups


async def resolve_approver(
    session: AsyncSession,
    company_id: int,
    document_type: str,
    amount: float,
) -> tuple[int, bool]:
    """Find the right approver for amount/type, respecting substitutions.

    Returns (approver_id, is_substitute).
    """
    from datetime import date
    today = date.today()

    matrix_result = await session.execute(
        select(CompanyApprovalMatrix)
        .where(
            CompanyApprovalMatrix.company_id == company_id,
            CompanyApprovalMatrix.document_type == document_type,
            CompanyApprovalMatrix.amount_threshold <= amount,
        )
        .order_by(CompanyApprovalMatrix.amount_threshold.desc())
        .limit(1)
    )
    matrix = matrix_result.scalar_one_or_none()
    if not matrix:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no approval rule found for this document/amount")

    approver_id = matrix.approver_id

    sub_result = await session.execute(
        select(ApprovalSubstitution).where(
            ApprovalSubstitution.company_id == company_id,
            ApprovalSubstitution.approver_id == approver_id,
            ApprovalSubstitution.valid_from <= today,
            ApprovalSubstitution.valid_to >= today,
        ).where(
            (ApprovalSubstitution.document_type == document_type)
            | (ApprovalSubstitution.document_type.is_(None))
        ).limit(1)
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        return sub.substitute_id, True
    return approver_id, False


async def lookup_transfer_price(
    session: AsyncSession,
    from_id: int,
    to_id: int,
    category: str | None,
    base_cost: float,
) -> dict:
    """Look up transfer price for an IC transaction."""
    stmt = (
        select(TransferPriceRule)
        .where(
            TransferPriceRule.from_company_id == from_id,
            TransferPriceRule.to_company_id == to_id,
            TransferPriceRule.active.is_(True),
            TransferPriceRule.deleted_at.is_(None),
        )
    )
    if category:
        stmt = stmt.where(
            (TransferPriceRule.product_category == category)
            | (TransferPriceRule.product_category.is_(None))
        )
    result = await session.execute(stmt.limit(1))
    rule = result.scalar_one_or_none()

    if not rule:
        return {
            "base_cost": base_cost,
            "markup_pct": 0.0,
            "transfer_price": base_cost,
            "method": "none",
            "rule_id": None,
        }

    markup = float(rule.markup_pct)
    transfer_price = round(base_cost * (1 + markup / 100), 4)
    return {
        "base_cost": base_cost,
        "markup_pct": markup,
        "transfer_price": transfer_price,
        "method": rule.method,
        "rule_id": rule.id,
    }


async def compute_rebate_accrual(
    session: AsyncSession,
    group_vendor_id: int,
    period: str,
    ytd_spend: float,
) -> VolumeRebateAccrual:
    """Compute and upsert a rebate accrual for the given period."""
    tiers_result = await session.execute(
        select(VolumeRebateTier).where(VolumeRebateTier.group_vendor_id == group_vendor_id)
    )
    tiers = [
        {"min_spend": float(t.min_spend), "rebate_pct": float(t.rebate_pct), "tier_label": t.tier_label}
        for t in tiers_result.scalars().all()
    ]
    matched = match_rebate_tier(tiers, ytd_spend)
    rebate_pct = matched["rebate_pct"] if matched else 0.0
    tier_label = matched["tier_label"] if matched else None
    accrued = round(ytd_spend * rebate_pct / 100, 2)

    existing = (
        await session.execute(
            select(VolumeRebateAccrual).where(
                VolumeRebateAccrual.group_vendor_id == group_vendor_id,
                VolumeRebateAccrual.period == period,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.accrued_amount = accrued
        existing.tier_matched = tier_label
        existing.snapshot_at = datetime.now(UTC)
        await session.flush()
        return existing

    accrual = VolumeRebateAccrual(
        group_vendor_id=group_vendor_id,
        period=period,
        accrued_amount=accrued,
        tier_matched=tier_label,
        snapshot_at=datetime.now(UTC),
    )
    session.add(accrual)
    await session.flush()
    return accrual


async def validate_cost_allocation(
    session: AsyncSession, allocation: CrossCompanyCostAllocation
) -> CrossCompanyCostAllocation:
    """draft → validated."""
    try:
        allocation.transition("validated")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    allocation.validated_at = datetime.now(UTC)
    await session.flush()
    return allocation


async def submit_compliance(
    session: AsyncSession, cal: ComplianceCalendar, ref_number: str | None
) -> ComplianceCalendar:
    """pending → submitted."""
    try:
        cal.transition("submitted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    cal.submitted_at = datetime.now(UTC)
    cal.ref_number = ref_number
    await session.flush()
    return cal


async def accept_compliance(
    session: AsyncSession, cal: ComplianceCalendar
) -> ComplianceCalendar:
    """submitted → accepted."""
    try:
        cal.transition("accepted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.flush()
    return cal

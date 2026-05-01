"""Service helpers for Phase 12 group extras.

All public functions are pure where possible (or take a session and return
a model row).  Heavy aggregation jobs (LTV refresh, vendor spend rollup)
get triggered explicitly by a scheduled task — these helpers do the
single-call computation only.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.group.models_finance import (
    BankAccount,
    CashForecastSnapshot,
    CashPool,
    CashPoolMember,
)
from backend.modules.group.models_governance import (
    ApprovalSubstitution,
    BrandLicense,
    SkuBridge,
    SkuBridgeMember,
    TransferPricingAgreement,
)
from backend.modules.group.models_partner import (
    CrossCompanyCustomer,
    CrossCompanyCustomerLink,
    CrossCompanyVendor,
    CrossCompanyVendorLink,
    VolumeRebateAccrual,
    VolumeRebateTier,
)


# ── Volume rebate tier matching ────────────────────────────────────────


def match_rebate_tier(
    tiers: list[dict],
    total_spend: float,
) -> dict | None:
    """Pick the highest tier whose ``min_spend ≤ total_spend < max_spend``.

    Pure function — ``tiers`` is a list of dicts with ``min_spend``,
    ``max_spend`` (None = +inf), and ``rebate_pct``.  Returns the matched
    tier (with all fields preserved) or ``None`` if no tier qualifies.
    """
    qualifying = [
        t
        for t in tiers
        if float(t["min_spend"]) <= total_spend
        and (t["max_spend"] is None or total_spend < float(t["max_spend"]))
    ]
    if not qualifying:
        return None
    # If multiple tiers overlap (shouldn't happen), prefer the highest min_spend
    return max(qualifying, key=lambda t: float(t["min_spend"]))


async def accrue_rebate(
    session: AsyncSession,
    vendor_profile_id: int,
    period_kind: str,
    period_start: date,
    period_end: date,
    total_group_spend: float,
) -> VolumeRebateAccrual:
    """Compute the accrual for a (vendor, period) and upsert the snapshot.

    Picks the matching tier, computes ``accrued_rebate = total_spend ×
    rebate_pct / 100``, and writes (or updates) the snapshot row.
    """
    profile = await session.get(CrossCompanyVendor, vendor_profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vendor profile not found")

    tier_stmt = (
        select(VolumeRebateTier)
        .where(
            VolumeRebateTier.vendor_profile_id == vendor_profile_id,
            VolumeRebateTier.period_kind == period_kind,
            VolumeRebateTier.active.is_(True),
        )
    )
    tier_rows = (await session.execute(tier_stmt)).scalars().all()
    tier_dicts = [
        {
            "min_spend": float(t.min_spend),
            "max_spend": float(t.max_spend) if t.max_spend is not None else None,
            "rebate_pct": float(t.rebate_pct),
        }
        for t in tier_rows
    ]
    tier = match_rebate_tier(tier_dicts, total_group_spend)
    matched_pct = float(tier["rebate_pct"]) if tier else 0.0
    accrued = round(total_group_spend * matched_pct / 100, 2)

    # Upsert the snapshot
    existing_stmt = select(VolumeRebateAccrual).where(
        VolumeRebateAccrual.vendor_profile_id == vendor_profile_id,
        VolumeRebateAccrual.period_kind == period_kind,
        VolumeRebateAccrual.period_start == period_start,
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing is None:
        snap = VolumeRebateAccrual(
            vendor_profile_id=vendor_profile_id,
            period_kind=period_kind,
            period_start=period_start,
            period_end=period_end,
            total_group_spend=total_group_spend,
            matched_tier_pct=matched_pct,
            accrued_rebate=accrued,
        )
        session.add(snap)
    else:
        existing.period_end = period_end
        existing.total_group_spend = total_group_spend
        existing.matched_tier_pct = matched_pct
        existing.accrued_rebate = accrued
        snap = existing
    await session.flush()
    return snap


# ── Cash forecast computation ──────────────────────────────────────────


def classify_cash_risk(
    projected_balance: float,
    target_balance: float,
    threshold_pct: float = 20,
) -> str:
    """Decide a `risk_flag` for a forecast snapshot.

    Returns one of: ``ok``, ``low``, ``critical``.  ``critical`` when
    projected balance is negative; ``low`` when within ``threshold_pct``%
    of target; otherwise ``ok``.
    """
    if projected_balance < 0:
        return "critical"
    if target_balance > 0:
        delta_pct = (target_balance - projected_balance) / target_balance * 100
        if delta_pct >= threshold_pct:
            return "low"
    return "ok"


async def take_cash_forecast(
    session: AsyncSession,
    company_id: int,
    forecast_date: date,
    horizon_days: int,
    opening_balance: float,
    cash_in: float,
    cash_out: float,
    currency: str = "THB",
    breakdown: dict | None = None,
) -> CashForecastSnapshot:
    """Upsert a cash-forecast snapshot.

    Idempotent: re-running with the same (company_id, forecast_date,
    horizon_days) overwrites the row instead of duplicating.
    """
    projected = opening_balance + cash_in - cash_out
    flag = classify_cash_risk(projected, target_balance=opening_balance)

    existing = await session.execute(
        select(CashForecastSnapshot).where(
            CashForecastSnapshot.company_id == company_id,
            CashForecastSnapshot.forecast_date == forecast_date,
            CashForecastSnapshot.horizon_days == horizon_days,
        )
    )
    snap = existing.scalar_one_or_none()
    if snap is None:
        snap = CashForecastSnapshot(
            company_id=company_id,
            forecast_date=forecast_date,
            horizon_days=horizon_days,
            currency=currency,
            opening_balance=opening_balance,
            cash_in=cash_in,
            cash_out=cash_out,
            projected_balance=projected,
            risk_flag=flag,
            breakdown=breakdown,
        )
        session.add(snap)
    else:
        snap.opening_balance = opening_balance
        snap.cash_in = cash_in
        snap.cash_out = cash_out
        snap.projected_balance = projected
        snap.risk_flag = flag
        snap.currency = currency
        snap.breakdown = breakdown
    await session.flush()
    return snap


# ── SKU bridge resolution ──────────────────────────────────────────────


async def resolve_sku(
    session: AsyncSession,
    company_id: int,
    master_sku: str | None = None,
    local_sku: str | None = None,
    local_product_id: int | None = None,
) -> dict:
    """Look up the (master, local) pair for one company.

    Caller passes any one of master_sku / local_sku / local_product_id.
    Returns dict with ``matched`` flag plus the resolved fields.
    """
    if not (master_sku or local_sku or local_product_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "must provide master_sku, local_sku, or local_product_id",
        )

    stmt = (
        select(SkuBridge, SkuBridgeMember)
        .join(SkuBridgeMember, SkuBridgeMember.bridge_id == SkuBridge.id)
        .where(SkuBridgeMember.company_id == company_id)
    )
    if master_sku:
        stmt = stmt.where(SkuBridge.master_sku == master_sku)
    if local_sku:
        stmt = stmt.where(SkuBridgeMember.local_sku == local_sku)
    if local_product_id:
        stmt = stmt.where(SkuBridgeMember.local_product_id == local_product_id)

    row = (await session.execute(stmt)).first()
    if row is None:
        return {
            "matched": False,
            "bridge_id": None,
            "master_sku": master_sku,
            "local_product_id": local_product_id,
            "local_sku": local_sku,
        }

    bridge, member = row
    return {
        "matched": True,
        "bridge_id": bridge.id,
        "master_sku": bridge.master_sku,
        "local_product_id": member.local_product_id,
        "local_sku": member.local_sku,
    }


# ── Transfer-pricing lookup ────────────────────────────────────────────


async def lookup_transfer_pricing(
    session: AsyncSession,
    from_company_id: int,
    to_company_id: int,
    product_category_id: int | None = None,
    on_date: date | None = None,
) -> dict:
    """Find the most-specific active transfer-pricing rule for the trio.

    Priority: (from, to, category) > (from, to, NULL category).
    Window: ``valid_from <= on_date <= valid_to`` (or valid_to NULL).
    """
    on_date = on_date or date.today()

    base_filter = and_(
        TransferPricingAgreement.from_company_id == from_company_id,
        TransferPricingAgreement.to_company_id == to_company_id,
        TransferPricingAgreement.active.is_(True),
        TransferPricingAgreement.valid_from <= on_date,
        or_(
            TransferPricingAgreement.valid_to.is_(None),
            TransferPricingAgreement.valid_to >= on_date,
        ),
    )

    # Specific category first
    if product_category_id is not None:
        stmt = select(TransferPricingAgreement).where(
            base_filter,
            TransferPricingAgreement.product_category_id == product_category_id,
        )
        agreement = (await session.execute(stmt)).scalar_one_or_none()
        if agreement is not None:
            return _agreement_to_result(agreement)

    # Fallback to NULL-category rule
    stmt = select(TransferPricingAgreement).where(
        base_filter,
        TransferPricingAgreement.product_category_id.is_(None),
    )
    agreement = (await session.execute(stmt)).scalar_one_or_none()
    if agreement is not None:
        return _agreement_to_result(agreement)

    return {
        "matched": False,
        "agreement_id": None,
        "method": None,
        "markup_pct": None,
        "fixed_price": None,
    }


def _agreement_to_result(agreement: TransferPricingAgreement) -> dict:
    return {
        "matched": True,
        "agreement_id": agreement.id,
        "method": agreement.method,
        "markup_pct": float(agreement.markup_pct),
        "fixed_price": float(agreement.fixed_price) if agreement.fixed_price is not None else None,
    }


# ── Approver substitution ──────────────────────────────────────────────


async def resolve_approver(
    session: AsyncSession,
    user_id: int,
    on_date: date | None = None,
    document_type: str | None = None,
) -> dict:
    """If ``user_id`` has an active substitution rule, return the fallback.

    Otherwise the primary user is returned as the effective approver.
    A document_type-specific rule beats a global rule for the same user.
    """
    on_date = on_date or date.today()

    base_filter = and_(
        ApprovalSubstitution.primary_user_id == user_id,
        ApprovalSubstitution.active.is_(True),
        ApprovalSubstitution.valid_from <= on_date,
        ApprovalSubstitution.valid_to >= on_date,
    )

    if document_type is not None:
        stmt = select(ApprovalSubstitution).where(
            base_filter,
            ApprovalSubstitution.document_type == document_type,
        )
        sub = (await session.execute(stmt)).scalar_one_or_none()
        if sub is not None:
            return _substitution_to_result(user_id, sub)

    stmt = select(ApprovalSubstitution).where(
        base_filter,
        ApprovalSubstitution.document_type.is_(None),
    )
    sub = (await session.execute(stmt)).scalar_one_or_none()
    if sub is not None:
        return _substitution_to_result(user_id, sub)

    return {
        "primary_user_id": user_id,
        "effective_user_id": user_id,
        "substituted": False,
        "substitution_id": None,
        "reason": None,
    }


def _substitution_to_result(primary_user_id: int, sub: ApprovalSubstitution) -> dict:
    return {
        "primary_user_id": primary_user_id,
        "effective_user_id": sub.fallback_user_id,
        "substituted": True,
        "substitution_id": sub.id,
        "reason": sub.reason,
    }


# ── Brand license check ────────────────────────────────────────────────


async def is_company_licensed_for_brand(
    session: AsyncSession,
    company_id: int,
    brand_code: str,
    on_date: date | None = None,
) -> bool:
    """True if ``company_id`` has an active ``BrandLicense`` for ``brand_code``."""
    on_date = on_date or date.today()
    stmt = select(BrandLicense).where(
        BrandLicense.licensed_to_company_id == company_id,
        BrandLicense.brand_code == brand_code,
        BrandLicense.active.is_(True),
        BrandLicense.valid_from <= on_date,
        or_(
            BrandLicense.valid_to.is_(None),
            BrandLicense.valid_to >= on_date,
        ),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return row is not None

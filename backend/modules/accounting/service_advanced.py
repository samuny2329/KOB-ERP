"""Accounting advanced — depreciation, VAT close, FX revaluation maths."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.workflow import WorkflowError
from backend.modules.accounting.models_advanced import (
    DepreciationEntry,
    FixedAsset,
    FxRevaluation,
    VatLine,
    VatPeriod,
    WhtCertificate,
)


# ── VAT period close ───────────────────────────────────────────────────


async def calculate_vat_period(
    session: AsyncSession, period: VatPeriod
) -> VatPeriod:
    """Sum input/output lines, set net_payable, transition draft→calculated."""
    try:
        period.transition("calculated")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    sums_stmt = (
        select(VatLine.direction, func.coalesce(func.sum(VatLine.vat_amount), 0))
        .where(VatLine.period_id == period.id)
        .group_by(VatLine.direction)
    )
    sums = {direction: float(total) for direction, total in (await session.execute(sums_stmt)).all()}
    period.input_vat = round(sums.get("input", 0.0), 2)
    period.output_vat = round(sums.get("output", 0.0), 2)
    period.net_payable = round(period.output_vat - period.input_vat, 2)
    if period.net_payable < 0:
        period.credit_carried_forward = -period.net_payable
        period.net_payable = 0
    return period


async def submit_vat_period(
    session: AsyncSession,
    period: VatPeriod,
    submitted_by: int | None,
    rd_receipt_number: str | None = None,
) -> VatPeriod:
    try:
        period.transition("submitted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    period.submitted_at = datetime.now(UTC)
    period.submitted_by = submitted_by
    period.rd_receipt_number = rd_receipt_number
    return period


# ── WHT certificate sequencing ─────────────────────────────────────────


async def next_wht_sequence(
    session: AsyncSession,
    company_id: int,
    form_type: str,
    period_year: int,
) -> int:
    """Per (company, form_type, year) sequence — restarts at 1 each year.

    Used by WhtCertificate creation to allocate the next number.
    """
    stmt = select(func.coalesce(func.max(WhtCertificate.sequence_number), 0)).where(
        WhtCertificate.company_id == company_id,
        WhtCertificate.form_type == form_type,
        WhtCertificate.period_year == period_year,
    )
    last = (await session.execute(stmt)).scalar()
    return int(last) + 1


# ── Fixed asset depreciation ───────────────────────────────────────────


def compute_monthly_depreciation(
    method: str,
    acquisition_cost: float,
    salvage_value: float,
    useful_life_months: int,
) -> float:
    """Pure function — monthly depreciation amount.

    Methods supported in v1:
      - straight_line: (cost - salvage) / months
      - declining_balance: cost × (rate × 2) / 12 — simplified DDB to monthly
      - units_of_production: caller computes externally; raises if requested

    Declining-balance returns the *first-month* amount; subsequent months
    apply the same rate to the new book value (call repeatedly).
    """
    cost = float(acquisition_cost)
    salvage = float(salvage_value)
    months = int(useful_life_months)
    if months <= 0:
        raise ValueError("useful_life_months must be > 0")

    if method == "straight_line":
        return round((cost - salvage) / months, 2)
    if method == "declining_balance":
        # 200% DDB monthly equivalent: (1/months) × 2 × current_book_value
        # First month: 2 × cost / months
        return round(2 * cost / months, 2)
    if method == "units_of_production":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "units_of_production needs caller to supply per-period units",
        )
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST, f"unknown depreciation_method: {method!r}"
    )


async def generate_depreciation_schedule(
    session: AsyncSession, asset: FixedAsset
) -> list[DepreciationEntry]:
    """Create the full schedule for ``asset`` based on its method.

    Wipes any existing entries and writes fresh ones (idempotent).  Stops
    when book_value reaches salvage_value.  Caller posts JE rows
    separately when each month is closed.
    """
    # Wipe existing
    for e in list(asset.schedule):
        await session.delete(e)
    await session.flush()

    if asset.acquisition_date is None:
        raise HTTPException(400, "asset has no acquisition_date")

    cost = float(asset.acquisition_cost)
    salvage = float(asset.salvage_value)
    months = int(asset.useful_life_months)
    method = asset.depreciation_method

    book_value = cost
    accumulated = 0.0
    schedule: list[DepreciationEntry] = []

    year = asset.acquisition_date.year
    month = asset.acquisition_date.month

    for i in range(months):
        if method == "straight_line":
            amt = round((cost - salvage) / months, 2)
        elif method == "declining_balance":
            amt = round(2 * book_value / months, 2)
        else:
            amt = 0

        # Don't depreciate below salvage value
        if accumulated + amt > cost - salvage:
            amt = round((cost - salvage) - accumulated, 2)

        if amt <= 0:
            break

        accumulated = round(accumulated + amt, 2)
        book_value = round(cost - accumulated, 2)

        entry = DepreciationEntry(
            asset_id=asset.id,
            period_year=year,
            period_month=month,
            depreciation_amount=amt,
            accumulated_to_date=accumulated,
            book_value_after=book_value,
        )
        session.add(entry)
        schedule.append(entry)

        # Advance month
        month += 1
        if month > 12:
            month = 1
            year += 1

    asset.accumulated_depreciation = 0  # nothing posted yet
    asset.book_value = cost
    await session.flush()
    return schedule


async def post_depreciation_period(
    session: AsyncSession,
    asset: FixedAsset,
    period_year: int,
    period_month: int,
) -> DepreciationEntry:
    """Mark one schedule entry as posted (book it).

    Updates the asset's accumulated_depreciation + book_value.
    """
    stmt = select(DepreciationEntry).where(
        DepreciationEntry.asset_id == asset.id,
        DepreciationEntry.period_year == period_year,
        DepreciationEntry.period_month == period_month,
    )
    entry = (await session.execute(stmt)).scalar_one_or_none()
    if entry is None:
        raise HTTPException(404, "no depreciation entry for that period")
    if entry.posted_at is not None:
        raise HTTPException(409, "entry already posted")

    entry.posted_at = datetime.now(UTC)
    asset.accumulated_depreciation = entry.accumulated_to_date
    asset.book_value = entry.book_value_after

    if asset.book_value <= float(asset.salvage_value):
        try:
            asset.transition("fully_depreciated")
        except WorkflowError:
            pass  # already terminal or not in `in_use`

    return entry


# ── FX revaluation ─────────────────────────────────────────────────────


def compute_fx_revaluation(
    booked_balance_fc: float,
    booked_balance_thb: float,
    period_end_rate: float,
) -> tuple[float, float]:
    """Pure function — returns ``(revalued_thb, fx_gain_loss)``."""
    revalued = round(float(booked_balance_fc) * float(period_end_rate), 2)
    gain_loss = round(revalued - float(booked_balance_thb), 2)
    return revalued, gain_loss

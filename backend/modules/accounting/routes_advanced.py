"""Routes for accounting advanced (Phase 14)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.accounting.models_advanced import (
    DepreciationEntry,
    FixedAsset,
    FxRevaluation,
    VatLine,
    VatPeriod,
    WhtCertificate,
)
from backend.modules.accounting.schemas_advanced import (
    DepreciationCalcResult,
    DepreciationEntryRead,
    DepreciationGenerateRequest,
    FixedAssetCreate,
    FixedAssetRead,
    FxRevaluationCreate,
    FxRevaluationRead,
    VatLineCreate,
    VatLineRead,
    VatPeriodCreate,
    VatPeriodRead,
    WhtCertificateCreate,
    WhtCertificateRead,
)
from backend.modules.accounting.service_advanced import (
    calculate_vat_period,
    compute_fx_revaluation,
    compute_monthly_depreciation,
    generate_depreciation_schedule,
    next_wht_sequence,
    post_depreciation_period,
    submit_vat_period,
)


router = APIRouter(prefix="/accounting", tags=["accounting-advanced"])


# ── VAT periods ────────────────────────────────────────────────────────


@router.post("/vat-periods", response_model=VatPeriodRead, status_code=201)
async def create_vat_period(
    body: VatPeriodCreate, session: SessionDep, _user: CurrentUser
) -> VatPeriod:
    period = VatPeriod(**body.model_dump(), state="draft")
    session.add(period)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "vat period already exists") from exc
    return period


@router.get("/vat-periods", response_model=list[VatPeriodRead])
async def list_vat_periods(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
    state: str | None = None,
) -> list[VatPeriod]:
    stmt = (
        select(VatPeriod)
        .where(VatPeriod.deleted_at.is_(None))
        .options(selectinload(VatPeriod.lines))
        .order_by(desc(VatPeriod.period_year), desc(VatPeriod.period_month))
    )
    if company_id is not None:
        stmt = stmt.where(VatPeriod.company_id == company_id)
    if state is not None:
        stmt = stmt.where(VatPeriod.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/vat-periods/{period_id}/lines", response_model=VatLineRead, status_code=201)
async def add_vat_line(
    period_id: int,
    body: VatLineCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> VatLine:
    if (await session.get(VatPeriod, period_id)) is None:
        raise HTTPException(404, "vat period not found")
    line = VatLine(**body.model_dump(), period_id=period_id)
    session.add(line)
    await session.flush()
    return line


@router.post("/vat-periods/{period_id}/calculate", response_model=VatPeriodRead)
async def calc_vat(
    period_id: int, session: SessionDep, _user: CurrentUser
) -> VatPeriod:
    stmt = (
        select(VatPeriod)
        .where(VatPeriod.id == period_id)
        .options(selectinload(VatPeriod.lines))
    )
    period = (await session.execute(stmt)).scalar_one_or_none()
    if period is None:
        raise HTTPException(404, "vat period not found")
    return await calculate_vat_period(session, period)


@router.post("/vat-periods/{period_id}/submit", response_model=VatPeriodRead)
async def submit_vat(
    period_id: int,
    session: SessionDep,
    user: CurrentUser,
    rd_receipt_number: str | None = None,
) -> VatPeriod:
    stmt = (
        select(VatPeriod)
        .where(VatPeriod.id == period_id)
        .options(selectinload(VatPeriod.lines))
    )
    period = (await session.execute(stmt)).scalar_one_or_none()
    if period is None:
        raise HTTPException(404, "vat period not found")
    return await submit_vat_period(session, period, user.id, rd_receipt_number)


# ── WHT certificates ───────────────────────────────────────────────────


@router.post("/wht-certificates", response_model=WhtCertificateRead, status_code=201)
async def create_wht_certificate(
    body: WhtCertificateCreate, session: SessionDep, _user: CurrentUser
) -> WhtCertificate:
    seq = await next_wht_sequence(
        session, body.company_id, body.form_type, body.period_year
    )
    wht_amount = round(body.gross_amount * body.wht_rate_pct / 100, 2)
    cert = WhtCertificate(
        **body.model_dump(),
        sequence_number=seq,
        wht_amount=wht_amount,
    )
    session.add(cert)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "sequence collision (concurrent insert)") from exc
    return cert


@router.get("/wht-certificates", response_model=list[WhtCertificateRead])
async def list_wht_certificates(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
    period_year: int | None = None,
) -> list[WhtCertificate]:
    stmt = select(WhtCertificate).order_by(
        desc(WhtCertificate.period_year), desc(WhtCertificate.sequence_number)
    )
    if company_id is not None:
        stmt = stmt.where(WhtCertificate.company_id == company_id)
    if period_year is not None:
        stmt = stmt.where(WhtCertificate.period_year == period_year)
    return list((await session.execute(stmt)).scalars().all())


# ── Fixed assets ───────────────────────────────────────────────────────


@router.post("/fixed-assets", response_model=FixedAssetRead, status_code=201)
async def create_fixed_asset(
    body: FixedAssetCreate, session: SessionDep, _user: CurrentUser
) -> FixedAsset:
    asset = FixedAsset(
        **body.model_dump(),
        state="pending",
        accumulated_depreciation=0,
        book_value=body.acquisition_cost,
    )
    session.add(asset)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "asset_code already exists") from exc
    return asset


@router.get("/fixed-assets", response_model=list[FixedAssetRead])
async def list_fixed_assets(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
    state: str | None = None,
) -> list[FixedAsset]:
    stmt = (
        select(FixedAsset)
        .where(FixedAsset.deleted_at.is_(None))
        .options(selectinload(FixedAsset.schedule))
        .order_by(FixedAsset.asset_code)
    )
    if company_id is not None:
        stmt = stmt.where(FixedAsset.company_id == company_id)
    if state is not None:
        stmt = stmt.where(FixedAsset.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post(
    "/fixed-assets/{asset_id}/generate-schedule",
    response_model=list[DepreciationEntryRead],
)
async def generate_schedule(
    asset_id: int, session: SessionDep, _user: CurrentUser
) -> list[DepreciationEntry]:
    stmt = (
        select(FixedAsset)
        .where(FixedAsset.id == asset_id)
        .options(selectinload(FixedAsset.schedule))
    )
    asset = (await session.execute(stmt)).scalar_one_or_none()
    if asset is None:
        raise HTTPException(404, "asset not found")
    return await generate_depreciation_schedule(session, asset)


@router.post("/fixed-assets/depreciation/calc", response_model=DepreciationCalcResult)
async def calc_depreciation(
    body: DepreciationGenerateRequest, session: SessionDep, _user: CurrentUser
) -> DepreciationCalcResult:
    asset = await session.get(FixedAsset, body.asset_id)
    if asset is None:
        raise HTTPException(404, "asset not found")
    monthly = compute_monthly_depreciation(
        asset.depreciation_method,
        float(asset.acquisition_cost),
        float(asset.salvage_value),
        asset.useful_life_months,
    )
    return DepreciationCalcResult(
        asset_id=asset.id,
        method=asset.depreciation_method,
        monthly_amount=monthly,
        total_periods=asset.useful_life_months,
        total_depreciation=round(
            float(asset.acquisition_cost) - float(asset.salvage_value), 2
        ),
    )


@router.post(
    "/fixed-assets/{asset_id}/post-period",
    response_model=DepreciationEntryRead,
)
async def post_depreciation(
    asset_id: int,
    period_year: int,
    period_month: int,
    session: SessionDep,
    _user: CurrentUser,
) -> DepreciationEntry:
    stmt = (
        select(FixedAsset)
        .where(FixedAsset.id == asset_id)
        .options(selectinload(FixedAsset.schedule))
    )
    asset = (await session.execute(stmt)).scalar_one_or_none()
    if asset is None:
        raise HTTPException(404, "asset not found")
    return await post_depreciation_period(session, asset, period_year, period_month)


# ── FX revaluation ─────────────────────────────────────────────────────


@router.post("/fx-revaluations", response_model=FxRevaluationRead, status_code=201)
async def create_fx_revaluation(
    body: FxRevaluationCreate, session: SessionDep, _user: CurrentUser
) -> FxRevaluation:
    revalued, gain_loss = compute_fx_revaluation(
        body.booked_balance_fc, body.booked_balance_thb, body.period_end_rate
    )
    rev = FxRevaluation(
        **body.model_dump(),
        revalued_balance_thb=revalued,
        fx_gain_loss=gain_loss,
    )
    session.add(rev)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "fx revaluation already exists for this period/currency") from exc
    return rev


@router.get("/fx-revaluations", response_model=list[FxRevaluationRead])
async def list_fx_revaluations(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
    currency: str | None = None,
) -> list[FxRevaluation]:
    stmt = select(FxRevaluation).order_by(
        desc(FxRevaluation.period_year), desc(FxRevaluation.period_month)
    )
    if company_id is not None:
        stmt = stmt.where(FxRevaluation.company_id == company_id)
    if currency is not None:
        stmt = stmt.where(FxRevaluation.currency == currency)
    return list((await session.execute(stmt)).scalars().all())

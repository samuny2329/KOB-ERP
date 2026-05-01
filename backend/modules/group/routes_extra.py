"""Routes for Phase 12 group extras (partner profiles, finance, governance)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.group.models_finance import (
    BankAccount,
    CashForecastSnapshot,
    CashPool,
    CashPoolMember,
    GroupAccrual,
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
from backend.modules.group.schemas_extra import (
    ApprovalSubstitutionCreate,
    ApprovalSubstitutionRead,
    ApproverResolveRequest,
    ApproverResolveResult,
    BankAccountCreate,
    BankAccountRead,
    BrandLicenseCreate,
    BrandLicenseRead,
    CashForecastSnapshotCreate,
    CashForecastSnapshotRead,
    CashPoolCreate,
    CashPoolRead,
    CrossCompanyCustomerCreate,
    CrossCompanyCustomerLinkCreate,
    CrossCompanyCustomerLinkRead,
    CrossCompanyCustomerRead,
    CrossCompanyVendorCreate,
    CrossCompanyVendorLinkCreate,
    CrossCompanyVendorLinkRead,
    CrossCompanyVendorRead,
    GroupAccrualCreate,
    GroupAccrualRead,
    RebateAccrualCompute,
    SkuBridgeCreate,
    SkuBridgeRead,
    SkuBridgeResolveRequest,
    SkuBridgeResolveResult,
    TransferPricingAgreementCreate,
    TransferPricingAgreementRead,
    TransferPricingLookup,
    TransferPricingResult,
    VolumeRebateAccrualRead,
    VolumeRebateTierCreate,
    VolumeRebateTierRead,
)
from backend.modules.group.service_extra import (
    accrue_rebate,
    is_company_licensed_for_brand,
    lookup_transfer_pricing,
    resolve_approver,
    resolve_sku,
    take_cash_forecast,
)


router = APIRouter(prefix="/group", tags=["group-extra"])


# ── Cross-company customer ─────────────────────────────────────────────


@router.post("/customers", response_model=CrossCompanyCustomerRead, status_code=201)
async def create_xc_customer(
    body: CrossCompanyCustomerCreate, session: SessionDep, _user: CurrentUser
) -> CrossCompanyCustomer:
    payload = body.model_dump(exclude={"links"})
    profile = CrossCompanyCustomer(**payload, active=True)
    session.add(profile)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "group_code already exists") from exc
    for link in body.links:
        session.add(CrossCompanyCustomerLink(profile_id=profile.id, **link.model_dump()))
    await session.flush()
    await session.refresh(profile, attribute_names=["links"])
    return profile


@router.get("/customers", response_model=list[CrossCompanyCustomerRead])
async def list_xc_customers(
    session: SessionDep, _user: CurrentUser
) -> list[CrossCompanyCustomer]:
    stmt = (
        select(CrossCompanyCustomer)
        .where(CrossCompanyCustomer.deleted_at.is_(None))
        .options(selectinload(CrossCompanyCustomer.links))
        .order_by(CrossCompanyCustomer.group_code)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post(
    "/customers/{profile_id}/links",
    response_model=CrossCompanyCustomerLinkRead,
    status_code=201,
)
async def link_xc_customer(
    profile_id: int,
    body: CrossCompanyCustomerLinkCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> CrossCompanyCustomerLink:
    if (await session.get(CrossCompanyCustomer, profile_id)) is None:
        raise HTTPException(404, "profile not found")
    link = CrossCompanyCustomerLink(profile_id=profile_id, **body.model_dump())
    session.add(link)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "this company/customer already linked") from exc
    return link


# ── Cross-company vendor ───────────────────────────────────────────────


@router.post("/vendors", response_model=CrossCompanyVendorRead, status_code=201)
async def create_xc_vendor(
    body: CrossCompanyVendorCreate, session: SessionDep, _user: CurrentUser
) -> CrossCompanyVendor:
    payload = body.model_dump(exclude={"links"})
    profile = CrossCompanyVendor(**payload, active=True)
    session.add(profile)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "group_code already exists") from exc
    for link in body.links:
        session.add(CrossCompanyVendorLink(profile_id=profile.id, **link.model_dump()))
    await session.flush()
    await session.refresh(profile, attribute_names=["links"])
    return profile


@router.get("/vendors", response_model=list[CrossCompanyVendorRead])
async def list_xc_vendors(
    session: SessionDep, _user: CurrentUser
) -> list[CrossCompanyVendor]:
    stmt = (
        select(CrossCompanyVendor)
        .where(CrossCompanyVendor.deleted_at.is_(None))
        .options(selectinload(CrossCompanyVendor.links))
        .order_by(CrossCompanyVendor.group_code)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post(
    "/vendors/{profile_id}/links",
    response_model=CrossCompanyVendorLinkRead,
    status_code=201,
)
async def link_xc_vendor(
    profile_id: int,
    body: CrossCompanyVendorLinkCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> CrossCompanyVendorLink:
    if (await session.get(CrossCompanyVendor, profile_id)) is None:
        raise HTTPException(404, "profile not found")
    link = CrossCompanyVendorLink(profile_id=profile_id, **body.model_dump())
    session.add(link)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "this company/vendor already linked") from exc
    return link


# ── Volume rebate ──────────────────────────────────────────────────────


@router.post("/rebate-tiers", response_model=VolumeRebateTierRead, status_code=201)
async def create_rebate_tier(
    body: VolumeRebateTierCreate, session: SessionDep, _user: CurrentUser
) -> VolumeRebateTier:
    tier = VolumeRebateTier(**body.model_dump(), active=True)
    session.add(tier)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "tier with this min_spend already exists") from exc
    return tier


@router.get("/rebate-tiers", response_model=list[VolumeRebateTierRead])
async def list_rebate_tiers(
    session: SessionDep,
    _user: CurrentUser,
    vendor_profile_id: int | None = None,
) -> list[VolumeRebateTier]:
    stmt = select(VolumeRebateTier).where(VolumeRebateTier.deleted_at.is_(None))
    if vendor_profile_id is not None:
        stmt = stmt.where(VolumeRebateTier.vendor_profile_id == vendor_profile_id)
    return list((await session.execute(stmt.order_by(VolumeRebateTier.min_spend))).scalars().all())


@router.post("/rebate-accruals/compute", response_model=VolumeRebateAccrualRead)
async def compute_rebate_accrual(
    body: RebateAccrualCompute, session: SessionDep, _user: CurrentUser
) -> VolumeRebateAccrual:
    return await accrue_rebate(
        session,
        body.vendor_profile_id,
        body.period_kind,
        body.period_start,
        body.period_end,
        body.total_group_spend,
    )


@router.get("/rebate-accruals", response_model=list[VolumeRebateAccrualRead])
async def list_rebate_accruals(
    session: SessionDep,
    _user: CurrentUser,
    vendor_profile_id: int | None = None,
) -> list[VolumeRebateAccrual]:
    stmt = select(VolumeRebateAccrual).order_by(desc(VolumeRebateAccrual.period_start))
    if vendor_profile_id is not None:
        stmt = stmt.where(VolumeRebateAccrual.vendor_profile_id == vendor_profile_id)
    return list((await session.execute(stmt)).scalars().all())


# ── Bank accounts + cash pools ─────────────────────────────────────────


@router.post("/bank-accounts", response_model=BankAccountRead, status_code=201)
async def create_bank_account(
    body: BankAccountCreate, session: SessionDep, _user: CurrentUser
) -> BankAccount:
    payload = body.model_dump()
    payload["available_balance"] = payload.get("current_balance", 0)
    acct = BankAccount(**payload, active=True)
    session.add(acct)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "account_number already exists for this company") from exc
    return acct


@router.get("/bank-accounts", response_model=list[BankAccountRead])
async def list_bank_accounts(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
) -> list[BankAccount]:
    stmt = select(BankAccount).where(BankAccount.deleted_at.is_(None))
    if company_id is not None:
        stmt = stmt.where(BankAccount.company_id == company_id)
    return list((await session.execute(stmt.order_by(BankAccount.bank_name))).scalars().all())


@router.post("/cash-pools", response_model=CashPoolRead, status_code=201)
async def create_cash_pool(
    body: CashPoolCreate, session: SessionDep, _user: CurrentUser
) -> CashPool:
    payload = body.model_dump(exclude={"members"})
    pool = CashPool(**payload, active=True)
    session.add(pool)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "cash pool code already exists") from exc
    for m in body.members:
        session.add(CashPoolMember(pool_id=pool.id, **m.model_dump()))
    await session.flush()
    await session.refresh(pool, attribute_names=["members"])
    return pool


@router.get("/cash-pools", response_model=list[CashPoolRead])
async def list_cash_pools(session: SessionDep, _user: CurrentUser) -> list[CashPool]:
    stmt = (
        select(CashPool)
        .where(CashPool.deleted_at.is_(None))
        .options(selectinload(CashPool.members))
        .order_by(CashPool.code)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post(
    "/cash-forecasts", response_model=CashForecastSnapshotRead, status_code=201
)
async def create_cash_forecast(
    body: CashForecastSnapshotCreate, session: SessionDep, _user: CurrentUser
) -> CashForecastSnapshot:
    return await take_cash_forecast(
        session,
        company_id=body.company_id,
        forecast_date=body.forecast_date,
        horizon_days=body.horizon_days,
        opening_balance=body.opening_balance,
        cash_in=body.cash_in,
        cash_out=body.cash_out,
        currency=body.currency,
        breakdown=body.breakdown,
    )


@router.get("/cash-forecasts", response_model=list[CashForecastSnapshotRead])
async def list_cash_forecasts(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
    risk_flag: str | None = None,
) -> list[CashForecastSnapshot]:
    stmt = select(CashForecastSnapshot).order_by(desc(CashForecastSnapshot.forecast_date))
    if company_id is not None:
        stmt = stmt.where(CashForecastSnapshot.company_id == company_id)
    if risk_flag is not None:
        stmt = stmt.where(CashForecastSnapshot.risk_flag == risk_flag)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/group-accruals", response_model=GroupAccrualRead, status_code=201)
async def create_group_accrual(
    body: GroupAccrualCreate, session: SessionDep, _user: CurrentUser
) -> GroupAccrual:
    accr = GroupAccrual(**body.model_dump(), state="active")
    session.add(accr)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "ref already exists") from exc
    return accr


@router.get("/group-accruals", response_model=list[GroupAccrualRead])
async def list_group_accruals(
    session: SessionDep, _user: CurrentUser, state: str | None = None
) -> list[GroupAccrual]:
    stmt = select(GroupAccrual).where(GroupAccrual.deleted_at.is_(None))
    if state is not None:
        stmt = stmt.where(GroupAccrual.state == state)
    return list((await session.execute(stmt.order_by(desc(GroupAccrual.id)))).scalars().all())


# ── SKU bridge ─────────────────────────────────────────────────────────


@router.post("/sku-bridges", response_model=SkuBridgeRead, status_code=201)
async def create_sku_bridge(
    body: SkuBridgeCreate, session: SessionDep, _user: CurrentUser
) -> SkuBridge:
    payload = body.model_dump(exclude={"members"})
    bridge = SkuBridge(**payload, active=True)
    session.add(bridge)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "master_sku already exists") from exc
    for m in body.members:
        session.add(SkuBridgeMember(bridge_id=bridge.id, **m.model_dump()))
    await session.flush()
    await session.refresh(bridge, attribute_names=["members"])
    return bridge


@router.get("/sku-bridges", response_model=list[SkuBridgeRead])
async def list_sku_bridges(session: SessionDep, _user: CurrentUser) -> list[SkuBridge]:
    stmt = (
        select(SkuBridge)
        .where(SkuBridge.deleted_at.is_(None))
        .options(selectinload(SkuBridge.members))
        .order_by(SkuBridge.master_sku)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("/sku-bridges/resolve", response_model=SkuBridgeResolveResult)
async def post_resolve_sku(
    body: SkuBridgeResolveRequest, session: SessionDep, _user: CurrentUser
) -> SkuBridgeResolveResult:
    return SkuBridgeResolveResult(
        **await resolve_sku(
            session,
            company_id=body.company_id,
            master_sku=body.master_sku,
            local_sku=body.local_sku,
            local_product_id=body.local_product_id,
        )
    )


# ── Brand license ──────────────────────────────────────────────────────


@router.post("/brand-licenses", response_model=BrandLicenseRead, status_code=201)
async def create_brand_license(
    body: BrandLicenseCreate, session: SessionDep, _user: CurrentUser
) -> BrandLicense:
    lic = BrandLicense(**body.model_dump(), active=True)
    session.add(lic)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "license overlaps with existing window") from exc
    return lic


@router.get("/brand-licenses", response_model=list[BrandLicenseRead])
async def list_brand_licenses(
    session: SessionDep,
    _user: CurrentUser,
    licensed_to_company_id: int | None = None,
    brand_code: str | None = None,
) -> list[BrandLicense]:
    stmt = select(BrandLicense).where(BrandLicense.deleted_at.is_(None))
    if licensed_to_company_id is not None:
        stmt = stmt.where(BrandLicense.licensed_to_company_id == licensed_to_company_id)
    if brand_code is not None:
        stmt = stmt.where(BrandLicense.brand_code == brand_code)
    return list((await session.execute(stmt.order_by(BrandLicense.brand_code))).scalars().all())


@router.get("/brand-licenses/check")
async def check_brand_license(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int,
    brand_code: str,
    on_date: date | None = None,
) -> dict[str, bool]:
    return {
        "licensed": await is_company_licensed_for_brand(
            session, company_id, brand_code, on_date
        )
    }


# ── Transfer pricing ───────────────────────────────────────────────────


@router.post(
    "/transfer-pricing", response_model=TransferPricingAgreementRead, status_code=201
)
async def create_transfer_pricing(
    body: TransferPricingAgreementCreate, session: SessionDep, _user: CurrentUser
) -> TransferPricingAgreement:
    agreement = TransferPricingAgreement(**body.model_dump(), active=True)
    session.add(agreement)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "transfer pricing window overlaps existing rule") from exc
    return agreement


@router.get(
    "/transfer-pricing", response_model=list[TransferPricingAgreementRead]
)
async def list_transfer_pricing(
    session: SessionDep,
    _user: CurrentUser,
    from_company_id: int | None = None,
    to_company_id: int | None = None,
) -> list[TransferPricingAgreement]:
    stmt = select(TransferPricingAgreement).where(
        TransferPricingAgreement.deleted_at.is_(None)
    )
    if from_company_id is not None:
        stmt = stmt.where(TransferPricingAgreement.from_company_id == from_company_id)
    if to_company_id is not None:
        stmt = stmt.where(TransferPricingAgreement.to_company_id == to_company_id)
    return list((await session.execute(stmt.order_by(TransferPricingAgreement.valid_from))).scalars().all())


@router.post("/transfer-pricing/lookup", response_model=TransferPricingResult)
async def post_transfer_pricing_lookup(
    body: TransferPricingLookup, session: SessionDep, _user: CurrentUser
) -> TransferPricingResult:
    return TransferPricingResult(
        **await lookup_transfer_pricing(
            session,
            body.from_company_id,
            body.to_company_id,
            body.product_category_id,
            body.on_date,
        )
    )


# ── Approval substitution ──────────────────────────────────────────────


@router.post(
    "/approval-substitutions", response_model=ApprovalSubstitutionRead, status_code=201
)
async def create_approval_substitution(
    body: ApprovalSubstitutionCreate, session: SessionDep, _user: CurrentUser
) -> ApprovalSubstitution:
    sub = ApprovalSubstitution(**body.model_dump(), active=True)
    session.add(sub)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "substitution overlaps with existing rule") from exc
    return sub


@router.get(
    "/approval-substitutions", response_model=list[ApprovalSubstitutionRead]
)
async def list_approval_substitutions(
    session: SessionDep,
    _user: CurrentUser,
    primary_user_id: int | None = None,
    active_only: bool = True,
) -> list[ApprovalSubstitution]:
    stmt = select(ApprovalSubstitution).where(ApprovalSubstitution.deleted_at.is_(None))
    if primary_user_id is not None:
        stmt = stmt.where(ApprovalSubstitution.primary_user_id == primary_user_id)
    if active_only:
        stmt = stmt.where(ApprovalSubstitution.active.is_(True))
    return list((await session.execute(stmt.order_by(desc(ApprovalSubstitution.valid_from)))).scalars().all())


@router.post("/approvers/resolve", response_model=ApproverResolveResult)
async def post_resolve_approver(
    body: ApproverResolveRequest, session: SessionDep, _user: CurrentUser
) -> ApproverResolveResult:
    return ApproverResolveResult(
        **await resolve_approver(
            session, body.user_id, body.on_date, body.document_type
        )
    )

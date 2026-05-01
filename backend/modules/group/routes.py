"""Group module routes — multi-company hierarchy, partner 360, finance, governance."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.db import SessionDep
from backend.core.models import Company
from backend.modules.group.models import (
    CompanyGroup,
    CompanyMembership,
    GroupKpiConfig,
    GroupKpiRollup,
    InventoryPool,
    InventoryPoolMember,
)
from backend.modules.group.models_finance import (
    BankAccount,
    CashForecastSnapshot,
    CashPool,
    CashPoolMember,
    CostAllocationLine,
    CrossCompanyCostAllocation,
    IntercompanyLoan,
    TransferPriceRule,
)
from backend.modules.group.models_governance import (
    ApprovalSubstitution,
    BrandLicense,
    CompanyApprovalMatrix,
    ComplianceCalendar,
)
from backend.modules.group.models_partner import (
    CrossCompanySkuBridge,
    GroupCustomerLink,
    GroupCustomerProfile,
    GroupVendorLink,
    GroupVendorProfile,
    SkuBridgeItem,
    VolumeRebateAccrual,
    VolumeRebateTier,
)
from backend.modules.group.schemas import (
    ApprovalSubstitutionCreate,
    ApprovalSubstitutionRead,
    BankAccountCreate,
    BankAccountRead,
    BrandLicenseCreate,
    BrandLicenseRead,
    CashForecastSnapshotCreate,
    CashForecastSnapshotRead,
    CashPoolCreate,
    CashPoolRead,
    CompanyApprovalMatrixCreate,
    CompanyApprovalMatrixRead,
    CompanyCreate,
    CompanyGroupCreate,
    CompanyGroupRead,
    CompanyMembershipCreate,
    CompanyMembershipRead,
    CompanyRead,
    ComplianceCalendarCreate,
    ComplianceCalendarRead,
    ComplianceSubmitPayload,
    CrossCompanyCostAllocationCreate,
    CrossCompanyCostAllocationRead,
    CrossCompanySkuBridgeCreate,
    CrossCompanySkuBridgeRead,
    GroupCustomerLinkCreate,
    GroupCustomerLinkRead,
    GroupCustomerProfileCreate,
    GroupCustomerProfileRead,
    GroupKpiRollupRead,
    GroupVendorLinkCreate,
    GroupVendorLinkRead,
    GroupVendorProfileCreate,
    GroupVendorProfileRead,
    IntercompanyLoanCreate,
    IntercompanyLoanRead,
    InventoryPoolCreate,
    InventoryPoolRead,
    KpiRollupComputePayload,
    RebateComputePayload,
    ResolveApproverPayload,
    ResolveApproverResult,
    SkuResolvePayload,
    SkuResolveResult,
    TransferPriceLookupPayload,
    TransferPriceLookupResult,
    TransferPriceRuleCreate,
    TransferPriceRuleRead,
    VolumeRebateAccrualRead,
    VolumeRebateTierCreate,
    VolumeRebateTierRead,
)
from backend.modules.group.service import (
    accept_compliance,
    classify_cash_risk,
    compute_rebate_accrual,
    lookup_transfer_price,
    resolve_approver,
    rollup_kpi,
    submit_compliance,
    validate_cost_allocation,
)

router = APIRouter(prefix="/group", tags=["group"])


# ── Companies ──────────────────────────────────────────────────────────


@router.post("/companies", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(payload: CompanyCreate, session: SessionDep):
    company = Company(**payload.model_dump())
    session.add(company)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "company code already exists")
    return company


@router.get("/companies", response_model=list[CompanyRead])
async def list_companies(session: SessionDep, active_only: bool = True):
    stmt = select(Company).where(Company.deleted_at.is_(None))
    if active_only:
        stmt = stmt.where(Company.active.is_(True))
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/companies/{company_id}", response_model=CompanyRead)
async def get_company(company_id: int, session: SessionDep):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "company not found")
    return company


# ── Company Groups ─────────────────────────────────────────────────────


@router.post("/company-groups", response_model=CompanyGroupRead, status_code=status.HTTP_201_CREATED)
async def create_company_group(payload: CompanyGroupCreate, session: SessionDep):
    grp = CompanyGroup(**payload.model_dump())
    session.add(grp)
    await session.flush()
    return grp


@router.get("/company-groups", response_model=list[CompanyGroupRead])
async def list_company_groups(session: SessionDep):
    result = await session.execute(select(CompanyGroup).where(CompanyGroup.deleted_at.is_(None)))
    return result.scalars().all()


# ── Memberships ────────────────────────────────────────────────────────


@router.post("/memberships", response_model=CompanyMembershipRead, status_code=status.HTTP_201_CREATED)
async def create_membership(payload: CompanyMembershipCreate, session: SessionDep):
    m = CompanyMembership(**payload.model_dump())
    session.add(m)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "membership already exists")
    return m


@router.get("/memberships", response_model=list[CompanyMembershipRead])
async def list_memberships(session: SessionDep, group_id: int | None = None):
    stmt = select(CompanyMembership).where(CompanyMembership.deleted_at.is_(None))
    if group_id:
        stmt = stmt.where(CompanyMembership.group_id == group_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Group Customer Profiles ────────────────────────────────────────────


@router.post("/customers", response_model=GroupCustomerProfileRead, status_code=status.HTTP_201_CREATED)
async def create_group_customer(payload: GroupCustomerProfileCreate, session: SessionDep):
    profile = GroupCustomerProfile(**payload.model_dump())
    session.add(profile)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "group_code already exists")
    return profile


@router.get("/customers", response_model=list[GroupCustomerProfileRead])
async def list_group_customers(session: SessionDep):
    result = await session.execute(select(GroupCustomerProfile).where(GroupCustomerProfile.deleted_at.is_(None)))
    return result.scalars().all()


@router.post("/customers/{profile_id}/links", response_model=GroupCustomerLinkRead, status_code=status.HTTP_201_CREATED)
async def create_customer_link(profile_id: int, payload: GroupCustomerLinkCreate, session: SessionDep):
    link = GroupCustomerLink(**{**payload.model_dump(), "group_customer_id": profile_id})
    session.add(link)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "link already exists")
    return link


@router.get("/customers/{profile_id}/links", response_model=list[GroupCustomerLinkRead])
async def list_customer_links(profile_id: int, session: SessionDep):
    result = await session.execute(
        select(GroupCustomerLink).where(
            GroupCustomerLink.group_customer_id == profile_id,
            GroupCustomerLink.deleted_at.is_(None),
        )
    )
    return result.scalars().all()


# ── Group Vendor Profiles ──────────────────────────────────────────────


@router.post("/vendors", response_model=GroupVendorProfileRead, status_code=status.HTTP_201_CREATED)
async def create_group_vendor(payload: GroupVendorProfileCreate, session: SessionDep):
    profile = GroupVendorProfile(**payload.model_dump())
    session.add(profile)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "group_code already exists")
    return profile


@router.get("/vendors", response_model=list[GroupVendorProfileRead])
async def list_group_vendors(session: SessionDep):
    result = await session.execute(select(GroupVendorProfile).where(GroupVendorProfile.deleted_at.is_(None)))
    return result.scalars().all()


@router.post("/vendors/{profile_id}/links", response_model=GroupVendorLinkRead, status_code=status.HTTP_201_CREATED)
async def create_vendor_link(profile_id: int, payload: GroupVendorLinkCreate, session: SessionDep):
    link = GroupVendorLink(**{**payload.model_dump(), "group_vendor_id": profile_id})
    session.add(link)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "link already exists")
    return link


@router.get("/vendors/{profile_id}/links", response_model=list[GroupVendorLinkRead])
async def list_vendor_links(profile_id: int, session: SessionDep):
    result = await session.execute(
        select(GroupVendorLink).where(
            GroupVendorLink.group_vendor_id == profile_id,
            GroupVendorLink.deleted_at.is_(None),
        )
    )
    return result.scalars().all()


# ── Volume Rebate ──────────────────────────────────────────────────────


@router.post("/rebate-tiers", response_model=VolumeRebateTierRead, status_code=status.HTTP_201_CREATED)
async def create_rebate_tier(payload: VolumeRebateTierCreate, session: SessionDep):
    tier = VolumeRebateTier(**payload.model_dump())
    session.add(tier)
    await session.flush()
    return tier


@router.get("/rebate-tiers", response_model=list[VolumeRebateTierRead])
async def list_rebate_tiers(session: SessionDep, group_vendor_id: int | None = None):
    stmt = select(VolumeRebateTier).where(VolumeRebateTier.deleted_at.is_(None))
    if group_vendor_id:
        stmt = stmt.where(VolumeRebateTier.group_vendor_id == group_vendor_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/rebate-accruals", response_model=list[VolumeRebateAccrualRead])
async def list_rebate_accruals(session: SessionDep, group_vendor_id: int | None = None):
    stmt = select(VolumeRebateAccrual).where(VolumeRebateAccrual.deleted_at.is_(None))
    if group_vendor_id:
        stmt = stmt.where(VolumeRebateAccrual.group_vendor_id == group_vendor_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/rebate-accruals/compute", response_model=VolumeRebateAccrualRead)
async def compute_rebate_accrual_endpoint(payload: RebateComputePayload, session: SessionDep):
    return await compute_rebate_accrual(session, payload.group_vendor_id, payload.period, payload.ytd_spend)


# ── SKU Bridge ─────────────────────────────────────────────────────────


@router.post("/sku-bridges", response_model=CrossCompanySkuBridgeRead, status_code=status.HTTP_201_CREATED)
async def create_sku_bridge(payload: CrossCompanySkuBridgeCreate, session: SessionDep):
    bridge = CrossCompanySkuBridge(master_sku=payload.master_sku, master_name=payload.master_name, active=payload.active)
    session.add(bridge)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "master_sku already exists")
    for item in payload.items:
        session.add(SkuBridgeItem(bridge_id=bridge.id, **item.model_dump()))
    await session.flush()
    await session.refresh(bridge, ["items"])
    return bridge


@router.get("/sku-bridges", response_model=list[CrossCompanySkuBridgeRead])
async def list_sku_bridges(session: SessionDep):
    result = await session.execute(
        select(CrossCompanySkuBridge)
        .where(CrossCompanySkuBridge.deleted_at.is_(None))
        .options(selectinload(CrossCompanySkuBridge.items))
    )
    return result.scalars().all()


@router.post("/sku-bridges/resolve", response_model=SkuResolveResult)
async def resolve_sku(payload: SkuResolvePayload, session: SessionDep):
    bridge_result = await session.execute(
        select(CrossCompanySkuBridge)
        .where(CrossCompanySkuBridge.master_sku == payload.master_sku)
        .options(selectinload(CrossCompanySkuBridge.items))
    )
    bridge = bridge_result.scalar_one_or_none()
    if not bridge:
        return SkuResolveResult(master_sku=payload.master_sku, company_id=payload.company_id, product_id=None, local_sku=None)
    item = next((i for i in bridge.items if i.company_id == payload.company_id), None)
    return SkuResolveResult(
        master_sku=payload.master_sku,
        company_id=payload.company_id,
        product_id=item.product_id if item else None,
        local_sku=item.local_sku if item else None,
    )


# ── Bank Accounts ──────────────────────────────────────────────────────


@router.post("/bank-accounts", response_model=BankAccountRead, status_code=status.HTTP_201_CREATED)
async def create_bank_account(payload: BankAccountCreate, session: SessionDep):
    account = BankAccount(**payload.model_dump())
    session.add(account)
    await session.flush()
    return account


@router.get("/bank-accounts", response_model=list[BankAccountRead])
async def list_bank_accounts(session: SessionDep, company_id: int | None = None):
    stmt = select(BankAccount).where(BankAccount.deleted_at.is_(None), BankAccount.active.is_(True))
    if company_id:
        stmt = stmt.where(BankAccount.company_id == company_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Cash Pools ─────────────────────────────────────────────────────────


@router.post("/cash-pools", response_model=CashPoolRead, status_code=status.HTTP_201_CREATED)
async def create_cash_pool(payload: CashPoolCreate, session: SessionDep):
    pool = CashPool(**payload.model_dump())
    session.add(pool)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "pool name already exists")
    return pool


@router.get("/cash-pools", response_model=list[CashPoolRead])
async def list_cash_pools(session: SessionDep):
    result = await session.execute(select(CashPool).where(CashPool.deleted_at.is_(None)))
    return result.scalars().all()


# ── Cash Forecasts ─────────────────────────────────────────────────────


@router.post("/cash-forecasts", response_model=CashForecastSnapshotRead, status_code=status.HTTP_201_CREATED)
async def create_cash_forecast(payload: CashForecastSnapshotCreate, session: SessionDep):
    snapshot = CashForecastSnapshot(**payload.model_dump())
    snapshot.risk_flag = classify_cash_risk(payload.closing, 0)
    session.add(snapshot)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "forecast already exists for this company/date")
    return snapshot


@router.get("/cash-forecasts", response_model=list[CashForecastSnapshotRead])
async def list_cash_forecasts(session: SessionDep, company_id: int | None = None):
    stmt = select(CashForecastSnapshot).where(CashForecastSnapshot.deleted_at.is_(None))
    if company_id:
        stmt = stmt.where(CashForecastSnapshot.company_id == company_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Intercompany Loans ─────────────────────────────────────────────────


@router.post("/intercompany-loans", response_model=IntercompanyLoanRead, status_code=status.HTTP_201_CREATED)
async def create_ic_loan(payload: IntercompanyLoanCreate, session: SessionDep):
    loan = IntercompanyLoan(**payload.model_dump())
    session.add(loan)
    await session.flush()
    return loan


@router.get("/intercompany-loans", response_model=list[IntercompanyLoanRead])
async def list_ic_loans(session: SessionDep, lender_id: int | None = None, borrower_id: int | None = None):
    stmt = select(IntercompanyLoan).where(IntercompanyLoan.deleted_at.is_(None))
    if lender_id:
        stmt = stmt.where(IntercompanyLoan.lender_id == lender_id)
    if borrower_id:
        stmt = stmt.where(IntercompanyLoan.borrower_id == borrower_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Cost Allocations ───────────────────────────────────────────────────


@router.post("/cost-allocations", response_model=CrossCompanyCostAllocationRead, status_code=status.HTTP_201_CREATED)
async def create_cost_allocation(payload: CrossCompanyCostAllocationCreate, session: SessionDep):
    alloc = CrossCompanyCostAllocation(
        name=payload.name, total_amount=payload.total_amount,
        basis=payload.basis, period=payload.period, state="draft",
    )
    session.add(alloc)
    await session.flush()
    for line in payload.lines:
        session.add(CostAllocationLine(allocation_id=alloc.id, **line.model_dump()))
    await session.flush()
    await session.refresh(alloc, ["lines"])
    return alloc


@router.get("/cost-allocations", response_model=list[CrossCompanyCostAllocationRead])
async def list_cost_allocations(session: SessionDep):
    result = await session.execute(
        select(CrossCompanyCostAllocation)
        .where(CrossCompanyCostAllocation.deleted_at.is_(None))
        .options(selectinload(CrossCompanyCostAllocation.lines))
    )
    return result.scalars().all()


@router.post("/cost-allocations/{alloc_id}/validate", response_model=CrossCompanyCostAllocationRead)
async def validate_allocation(alloc_id: int, session: SessionDep):
    alloc = await session.get(CrossCompanyCostAllocation, alloc_id, options=[selectinload(CrossCompanyCostAllocation.lines)])
    if not alloc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "allocation not found")
    return await validate_cost_allocation(session, alloc)


# ── Transfer Pricing ───────────────────────────────────────────────────


@router.post("/transfer-pricing", response_model=TransferPriceRuleRead, status_code=status.HTTP_201_CREATED)
async def create_transfer_price_rule(payload: TransferPriceRuleCreate, session: SessionDep):
    rule = TransferPriceRule(**payload.model_dump())
    session.add(rule)
    await session.flush()
    return rule


@router.get("/transfer-pricing", response_model=list[TransferPriceRuleRead])
async def list_transfer_price_rules(session: SessionDep, from_company_id: int | None = None):
    stmt = select(TransferPriceRule).where(TransferPriceRule.deleted_at.is_(None))
    if from_company_id:
        stmt = stmt.where(TransferPriceRule.from_company_id == from_company_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/transfer-pricing/lookup", response_model=TransferPriceLookupResult)
async def lookup_tp(payload: TransferPriceLookupPayload, session: SessionDep):
    result = await lookup_transfer_price(
        session, payload.from_company_id, payload.to_company_id, payload.product_category, payload.base_cost
    )
    return TransferPriceLookupResult(**result)


# ── Compliance Calendar ────────────────────────────────────────────────


@router.post("/compliance-calendar", response_model=ComplianceCalendarRead, status_code=status.HTTP_201_CREATED)
async def create_compliance_entry(payload: ComplianceCalendarCreate, session: SessionDep):
    entry = ComplianceCalendar(**payload.model_dump(), state="pending")
    session.add(entry)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "compliance entry already exists for this filing/period")
    return entry


@router.get("/compliance-calendar", response_model=list[ComplianceCalendarRead])
async def list_compliance_calendar(session: SessionDep, company_id: int | None = None, state: str | None = None):
    stmt = select(ComplianceCalendar).where(ComplianceCalendar.deleted_at.is_(None))
    if company_id:
        stmt = stmt.where(ComplianceCalendar.company_id == company_id)
    if state:
        stmt = stmt.where(ComplianceCalendar.state == state)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/compliance-calendar/{entry_id}/submit", response_model=ComplianceCalendarRead)
async def submit_compliance_endpoint(entry_id: int, payload: ComplianceSubmitPayload, session: SessionDep):
    entry = await session.get(ComplianceCalendar, entry_id)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "compliance entry not found")
    return await submit_compliance(session, entry, payload.ref_number)


@router.post("/compliance-calendar/{entry_id}/accept", response_model=ComplianceCalendarRead)
async def accept_compliance_endpoint(entry_id: int, session: SessionDep):
    entry = await session.get(ComplianceCalendar, entry_id)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "compliance entry not found")
    return await accept_compliance(session, entry)


# ── Approval Matrix ────────────────────────────────────────────────────


@router.post("/approval-matrix", response_model=CompanyApprovalMatrixRead, status_code=status.HTTP_201_CREATED)
async def create_approval_matrix(payload: CompanyApprovalMatrixCreate, session: SessionDep):
    matrix = CompanyApprovalMatrix(**payload.model_dump())
    session.add(matrix)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "approval rule already exists")
    return matrix


@router.get("/approval-matrix", response_model=list[CompanyApprovalMatrixRead])
async def list_approval_matrix(session: SessionDep, company_id: int | None = None):
    stmt = select(CompanyApprovalMatrix).where(CompanyApprovalMatrix.deleted_at.is_(None))
    if company_id:
        stmt = stmt.where(CompanyApprovalMatrix.company_id == company_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Approval Substitutions ─────────────────────────────────────────────


@router.post("/approval-substitutions", response_model=ApprovalSubstitutionRead, status_code=status.HTTP_201_CREATED)
async def create_substitution(payload: ApprovalSubstitutionCreate, session: SessionDep):
    sub = ApprovalSubstitution(**payload.model_dump())
    session.add(sub)
    await session.flush()
    return sub


@router.get("/approval-substitutions", response_model=list[ApprovalSubstitutionRead])
async def list_substitutions(session: SessionDep, company_id: int | None = None):
    stmt = select(ApprovalSubstitution).where(ApprovalSubstitution.deleted_at.is_(None))
    if company_id:
        stmt = stmt.where(ApprovalSubstitution.company_id == company_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/approvers/resolve", response_model=ResolveApproverResult)
async def resolve_approver_endpoint(payload: ResolveApproverPayload, session: SessionDep):
    approver_id, is_sub = await resolve_approver(session, payload.company_id, payload.document_type, payload.amount)
    return ResolveApproverResult(approver_id=approver_id, is_substitute=is_sub)


# ── Brand Licenses ─────────────────────────────────────────────────────


@router.post("/brand-licenses", response_model=BrandLicenseRead, status_code=status.HTTP_201_CREATED)
async def create_brand_license(payload: BrandLicenseCreate, session: SessionDep):
    license_ = BrandLicense(**payload.model_dump())
    session.add(license_)
    await session.flush()
    return license_


@router.get("/brand-licenses", response_model=list[BrandLicenseRead])
async def list_brand_licenses(session: SessionDep, owner_company_id: int | None = None):
    stmt = select(BrandLicense).where(BrandLicense.deleted_at.is_(None), BrandLicense.active.is_(True))
    if owner_company_id:
        stmt = stmt.where(BrandLicense.owner_company_id == owner_company_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/brand-licenses/check")
async def check_brand_license(
    session: SessionDep,
    owner_company_id: int,
    licensee_company_id: int,
    brand_name: str,
):
    from datetime import date
    today = date.today()
    result = await session.execute(
        select(BrandLicense).where(
            BrandLicense.owner_company_id == owner_company_id,
            BrandLicense.licensee_company_id == licensee_company_id,
            BrandLicense.brand_name == brand_name,
            BrandLicense.active.is_(True),
            BrandLicense.valid_from <= today,
            BrandLicense.deleted_at.is_(None),
        )
    )
    license_ = result.scalar_one_or_none()
    return {"licensed": license_ is not None, "royalty_pct": float(license_.royalty_pct) if license_ else None}


# ── Group KPI ──────────────────────────────────────────────────────────


@router.get("/kpi-rollup", response_model=list[GroupKpiRollupRead])
async def list_kpi_rollup(session: SessionDep, company_id: int | None = None, period: str | None = None):
    stmt = select(GroupKpiRollup).where(GroupKpiRollup.deleted_at.is_(None))
    if company_id:
        stmt = stmt.where(GroupKpiRollup.company_id == company_id)
    if period:
        stmt = stmt.where(GroupKpiRollup.period == period)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/kpi-rollup/compute", response_model=list[GroupKpiRollupRead])
async def compute_kpi_rollup(payload: KpiRollupComputePayload, session: SessionDep):
    return await rollup_kpi(session, payload.group_id, payload.period, payload.metric_name)


# ── Inventory Pools ────────────────────────────────────────────────────


@router.post("/inventory-pools", response_model=InventoryPoolRead, status_code=status.HTTP_201_CREATED)
async def create_inventory_pool(payload: InventoryPoolCreate, session: SessionDep):
    pool = InventoryPool(**payload.model_dump())
    session.add(pool)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "pool name already exists")
    return pool


@router.get("/inventory-pools", response_model=list[InventoryPoolRead])
async def list_inventory_pools(session: SessionDep):
    result = await session.execute(select(InventoryPool).where(InventoryPool.deleted_at.is_(None)))
    return result.scalars().all()

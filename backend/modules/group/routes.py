"""HTTP routes for the group / multi-company module."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.group.models import (
    ApprovalMatrix,
    ApprovalMatrixRule,
    CompanyComplianceItem,
    CostAllocation,
    CostAllocationLine,
    GroupKpiSnapshot,
    InterCompanyLoan,
    InventoryPool,
    InventoryPoolMember,
    InventoryPoolRule,
    LoanInstallment,
    TaxGroup,
    TaxGroupMember,
)
from backend.modules.group.schemas import (
    ApprovalLookupRequest,
    ApprovalLookupResult,
    ApprovalMatrixCreate,
    ApprovalMatrixRead,
    ComplianceItemCreate,
    ComplianceItemRead,
    CostAllocationCreate,
    CostAllocationRead,
    GroupKpiRollup,
    GroupKpiSnapshotCreate,
    GroupKpiSnapshotRead,
    InterCompanyLoanCreate,
    InterCompanyLoanRead,
    InventoryPoolCreate,
    InventoryPoolMemberCreate,
    InventoryPoolMemberRead,
    InventoryPoolRead,
    InventoryPoolRuleCreate,
    InventoryPoolRuleRead,
    LoanRepayment,
    StockLookupOption,
    StockLookupRequest,
    TaxGroupCreate,
    TaxGroupRead,
)
from backend.modules.group.service import (
    activate_loan,
    calculate_allocation,
    companies_in_same_tax_group,
    lookup_approval,
    lookup_pool_stock,
    post_allocation,
    repay_installment,
    rollup_kpi,
)


router = APIRouter(prefix="/group", tags=["group"])


# ── Group KPI ──────────────────────────────────────────────────────────


@router.post("/kpi-snapshots", response_model=GroupKpiSnapshotRead, status_code=201)
async def create_kpi_snapshot(
    body: GroupKpiSnapshotCreate, session: SessionDep, _user: CurrentUser
) -> GroupKpiSnapshot:
    snap = GroupKpiSnapshot(**body.model_dump())
    session.add(snap)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "snapshot already exists for that company/metric/window") from exc
    return snap


@router.get("/kpi-snapshots", response_model=list[GroupKpiSnapshotRead])
async def list_kpi_snapshots(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
    metric: str | None = None,
) -> list[GroupKpiSnapshot]:
    stmt = select(GroupKpiSnapshot).order_by(desc(GroupKpiSnapshot.period_end))
    if company_id is not None:
        stmt = stmt.where(GroupKpiSnapshot.company_id == company_id)
    if metric is not None:
        stmt = stmt.where(GroupKpiSnapshot.metric == metric)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/kpi-rollup", response_model=GroupKpiRollup)
async def get_kpi_rollup(
    session: SessionDep,
    _user: CurrentUser,
    parent_company_id: int,
    metric: str,
    period_start: date,
    period_end: date,
) -> GroupKpiRollup:
    return GroupKpiRollup(
        **await rollup_kpi(session, parent_company_id, metric, period_start, period_end)
    )


# ── Inventory pool ─────────────────────────────────────────────────────


@router.post("/inventory-pools", response_model=InventoryPoolRead, status_code=201)
async def create_pool(
    body: InventoryPoolCreate, session: SessionDep, _user: CurrentUser
) -> InventoryPool:
    pool = InventoryPool(**body.model_dump(), active=True)
    session.add(pool)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "pool code already exists") from exc
    return pool


@router.get("/inventory-pools", response_model=list[InventoryPoolRead])
async def list_pools(session: SessionDep, _user: CurrentUser) -> list[InventoryPool]:
    return list(
        (
            await session.execute(
                select(InventoryPool).where(InventoryPool.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )


@router.post(
    "/inventory-pools/{pool_id}/members",
    response_model=InventoryPoolMemberRead,
    status_code=201,
)
async def add_pool_member(
    pool_id: int,
    body: InventoryPoolMemberCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> InventoryPoolMember:
    if (await session.get(InventoryPool, pool_id)) is None:
        raise HTTPException(404, "pool not found")
    member = InventoryPoolMember(**body.model_dump(), pool_id=pool_id)
    session.add(member)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "warehouse already in this pool") from exc
    return member


@router.post(
    "/inventory-pools/{pool_id}/rules",
    response_model=InventoryPoolRuleRead,
    status_code=201,
)
async def add_pool_rule(
    pool_id: int,
    body: InventoryPoolRuleCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> InventoryPoolRule:
    if (await session.get(InventoryPool, pool_id)) is None:
        raise HTTPException(404, "pool not found")
    rule = InventoryPoolRule(**body.model_dump(), pool_id=pool_id, active=True)
    session.add(rule)
    await session.flush()
    return rule


@router.post(
    "/inventory-pools/{pool_id}/lookup",
    response_model=list[StockLookupOption],
)
async def lookup_pool(
    pool_id: int,
    body: StockLookupRequest,
    session: SessionDep,
    _user: CurrentUser,
) -> list[StockLookupOption]:
    options = await lookup_pool_stock(session, pool_id, body.product_id, body.qty)
    return [StockLookupOption(**o) for o in options]


# ── Cost allocation ────────────────────────────────────────────────────


@router.post("/cost-allocations", response_model=CostAllocationRead, status_code=201)
async def create_allocation(
    body: CostAllocationCreate, session: SessionDep, _user: CurrentUser
) -> CostAllocation:
    payload = body.model_dump(exclude={"rules"})
    allocation = CostAllocation(**payload, state="draft")
    session.add(allocation)
    await session.flush()
    for line in body.rules:
        session.add(CostAllocationLine(allocation_id=allocation.id, **line.model_dump()))
    await session.flush()
    await session.refresh(allocation, attribute_names=["rules"])
    return allocation


@router.get("/cost-allocations", response_model=list[CostAllocationRead])
async def list_allocations(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
) -> list[CostAllocation]:
    stmt = (
        select(CostAllocation)
        .where(CostAllocation.deleted_at.is_(None))
        .options(selectinload(CostAllocation.rules))
        .order_by(desc(CostAllocation.id))
    )
    if state is not None:
        stmt = stmt.where(CostAllocation.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post(
    "/cost-allocations/{allocation_id}/calculate", response_model=CostAllocationRead
)
async def calculate_alloc(
    allocation_id: int, session: SessionDep, _user: CurrentUser
) -> CostAllocation:
    stmt = (
        select(CostAllocation)
        .where(CostAllocation.id == allocation_id)
        .options(selectinload(CostAllocation.rules))
    )
    alloc = (await session.execute(stmt)).scalar_one_or_none()
    if alloc is None:
        raise HTTPException(404, "allocation not found")
    return await calculate_allocation(session, alloc)


@router.post("/cost-allocations/{allocation_id}/post", response_model=CostAllocationRead)
async def post_alloc(
    allocation_id: int, session: SessionDep, _user: CurrentUser
) -> CostAllocation:
    stmt = (
        select(CostAllocation)
        .where(CostAllocation.id == allocation_id)
        .options(selectinload(CostAllocation.rules))
    )
    alloc = (await session.execute(stmt)).scalar_one_or_none()
    if alloc is None:
        raise HTTPException(404, "allocation not found")
    return await post_allocation(session, alloc)


# ── Inter-company loans ────────────────────────────────────────────────


@router.post("/loans", response_model=InterCompanyLoanRead, status_code=201)
async def create_loan(
    body: InterCompanyLoanCreate, session: SessionDep, _user: CurrentUser
) -> InterCompanyLoan:
    payload = body.model_dump(exclude={"installments"})
    loan = InterCompanyLoan(**payload, state="draft", outstanding_balance=body.principal)
    session.add(loan)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "loan ref already exists") from exc

    for inst in body.installments:
        session.add(LoanInstallment(loan_id=loan.id, **inst.model_dump(), state="pending"))
    await session.flush()
    await session.refresh(loan, attribute_names=["installments"])
    return loan


@router.get("/loans", response_model=list[InterCompanyLoanRead])
async def list_loans(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
    lender_company_id: int | None = None,
    borrower_company_id: int | None = None,
) -> list[InterCompanyLoan]:
    stmt = (
        select(InterCompanyLoan)
        .where(InterCompanyLoan.deleted_at.is_(None))
        .options(selectinload(InterCompanyLoan.installments))
        .order_by(desc(InterCompanyLoan.id))
    )
    if state is not None:
        stmt = stmt.where(InterCompanyLoan.state == state)
    if lender_company_id is not None:
        stmt = stmt.where(InterCompanyLoan.lender_company_id == lender_company_id)
    if borrower_company_id is not None:
        stmt = stmt.where(InterCompanyLoan.borrower_company_id == borrower_company_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/loans/{loan_id}/activate", response_model=InterCompanyLoanRead)
async def post_activate_loan(
    loan_id: int, session: SessionDep, _user: CurrentUser
) -> InterCompanyLoan:
    stmt = (
        select(InterCompanyLoan)
        .where(InterCompanyLoan.id == loan_id)
        .options(selectinload(InterCompanyLoan.installments))
    )
    loan = (await session.execute(stmt)).scalar_one_or_none()
    if loan is None:
        raise HTTPException(404, "loan not found")
    return await activate_loan(session, loan)


@router.post("/loans/{loan_id}/repay", response_model=InterCompanyLoanRead)
async def post_repay(
    loan_id: int,
    body: LoanRepayment,
    session: SessionDep,
    _user: CurrentUser,
) -> InterCompanyLoan:
    stmt = (
        select(InterCompanyLoan)
        .where(InterCompanyLoan.id == loan_id)
        .options(selectinload(InterCompanyLoan.installments))
    )
    loan = (await session.execute(stmt)).scalar_one_or_none()
    if loan is None:
        raise HTTPException(404, "loan not found")
    await repay_installment(session, loan, body.installment_id, body.paid_amount, body.paid_date)
    return loan


# ── Tax group ──────────────────────────────────────────────────────────


@router.post("/tax-groups", response_model=TaxGroupRead, status_code=201)
async def create_tax_group(
    body: TaxGroupCreate, session: SessionDep, _user: CurrentUser
) -> TaxGroup:
    payload = body.model_dump(exclude={"members"})
    tg = TaxGroup(**payload, active=True)
    session.add(tg)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "tax group code already exists") from exc

    for m in body.members:
        session.add(TaxGroupMember(tax_group_id=tg.id, **m.model_dump()))
    await session.flush()
    await session.refresh(tg, attribute_names=["members"])
    return tg


@router.get("/tax-groups", response_model=list[TaxGroupRead])
async def list_tax_groups(session: SessionDep, _user: CurrentUser) -> list[TaxGroup]:
    return list(
        (
            await session.execute(
                select(TaxGroup)
                .where(TaxGroup.deleted_at.is_(None))
                .options(selectinload(TaxGroup.members))
                .order_by(TaxGroup.code)
            )
        )
        .scalars()
        .all()
    )


@router.get("/tax-groups/check")
async def check_tax_group(
    session: SessionDep,
    _user: CurrentUser,
    company_a_id: int,
    company_b_id: int,
    on_date: date | None = None,
) -> dict[str, bool]:
    return {
        "in_same_group": await companies_in_same_tax_group(
            session, company_a_id, company_b_id, on_date
        )
    }


# ── Approval matrix ────────────────────────────────────────────────────


@router.post("/approval-matrices", response_model=ApprovalMatrixRead, status_code=201)
async def create_approval_matrix(
    body: ApprovalMatrixCreate, session: SessionDep, _user: CurrentUser
) -> ApprovalMatrix:
    payload = body.model_dump(exclude={"rules"})
    matrix = ApprovalMatrix(**payload, active=True)
    session.add(matrix)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "matrix already exists for this company/document_type") from exc
    for r in body.rules:
        session.add(ApprovalMatrixRule(matrix_id=matrix.id, **r.model_dump(), active=True))
    await session.flush()
    await session.refresh(matrix, attribute_names=["rules"])
    return matrix


@router.get("/approval-matrices", response_model=list[ApprovalMatrixRead])
async def list_approval_matrices(
    session: SessionDep, _user: CurrentUser, company_id: int | None = None
) -> list[ApprovalMatrix]:
    stmt = (
        select(ApprovalMatrix)
        .where(ApprovalMatrix.deleted_at.is_(None))
        .options(selectinload(ApprovalMatrix.rules))
    )
    if company_id is not None:
        stmt = stmt.where(ApprovalMatrix.company_id == company_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/approval-matrices/lookup", response_model=ApprovalLookupResult)
async def lookup_matrix(
    body: ApprovalLookupRequest, session: SessionDep, _user: CurrentUser
) -> ApprovalLookupResult:
    return ApprovalLookupResult(
        **await lookup_approval(session, body.company_id, body.document_type, body.amount)
    )


# ── Compliance ─────────────────────────────────────────────────────────


@router.post("/compliance-items", response_model=ComplianceItemRead, status_code=201)
async def create_compliance_item(
    body: ComplianceItemCreate, session: SessionDep, _user: CurrentUser
) -> CompanyComplianceItem:
    item = CompanyComplianceItem(**body.model_dump(), state="pending")
    session.add(item)
    await session.flush()
    return item


@router.get("/compliance-items", response_model=list[ComplianceItemRead])
async def list_compliance_items(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
    state: str | None = None,
    overdue_only: bool = False,
) -> list[CompanyComplianceItem]:
    stmt = (
        select(CompanyComplianceItem)
        .where(CompanyComplianceItem.deleted_at.is_(None))
        .order_by(CompanyComplianceItem.due_date)
    )
    if company_id is not None:
        stmt = stmt.where(CompanyComplianceItem.company_id == company_id)
    if state is not None:
        stmt = stmt.where(CompanyComplianceItem.state == state)
    if overdue_only:
        stmt = stmt.where(CompanyComplianceItem.due_date < date.today())
        stmt = stmt.where(CompanyComplianceItem.state.in_(("pending", "in_progress", "overdue")))
    return list((await session.execute(stmt)).scalars().all())

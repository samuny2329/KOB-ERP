"""Routes for HR Phase 14 (Thai compliance + cross-company)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.hr.models import Employee, LeaveType
from backend.modules.hr.models_advanced import (
    EmployeeTransfer,
    LeaveEntitlement,
    OvertimeRecord,
    PndFiling,
    SsoContribution,
    SsoRegistration,
)
from backend.modules.hr.schemas_advanced import (
    EmployeeTransferCreate,
    EmployeeTransferRead,
    LeaveAccrualRequest,
    LeaveAccrualResult,
    LeaveEntitlementCreate,
    LeaveEntitlementRead,
    OvertimeCalcRequest,
    OvertimeCalcResult,
    OvertimeRecordCreate,
    OvertimeRecordRead,
    PndFilingCreate,
    PndFilingRead,
    SsoContributionCreate,
    SsoContributionRead,
    SsoRegistrationCreate,
    SsoRegistrationRead,
)
from backend.modules.hr.service_advanced import (
    calculate_pnd_filing,
    complete_employee_transfer,
    compute_overtime,
    compute_sso_amounts,
    resolve_leave_grant,
    submit_pnd_filing,
    years_of_service,
)


router = APIRouter(prefix="/hr", tags=["hr-advanced"])


# ── SSO ────────────────────────────────────────────────────────────────


@router.post("/sso-registrations", response_model=SsoRegistrationRead, status_code=201)
async def create_sso_registration(
    body: SsoRegistrationCreate, session: SessionDep, _user: CurrentUser
) -> SsoRegistration:
    reg = SsoRegistration(**body.model_dump(), active=True)
    session.add(reg)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "employee already registered or ssn duplicate") from exc
    return reg


@router.get("/sso-registrations", response_model=list[SsoRegistrationRead])
async def list_sso_registrations(
    session: SessionDep, _user: CurrentUser
) -> list[SsoRegistration]:
    return list(
        (
            await session.execute(
                select(SsoRegistration).where(SsoRegistration.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )


@router.post("/sso-contributions", response_model=SsoContributionRead, status_code=201)
async def create_sso_contribution(
    body: SsoContributionCreate, session: SessionDep, _user: CurrentUser
) -> SsoContribution:
    employee_amt, employer_amt = compute_sso_amounts(body.gross_wage)
    contrib = SsoContribution(
        **body.model_dump(),
        employee_amount=employee_amt,
        employer_amount=employer_amt,
    )
    session.add(contrib)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "contribution already exists for this period") from exc
    return contrib


@router.get("/sso-contributions", response_model=list[SsoContributionRead])
async def list_sso_contributions(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
    employee_id: int | None = None,
) -> list[SsoContribution]:
    stmt = select(SsoContribution).order_by(
        desc(SsoContribution.period_year), desc(SsoContribution.period_month)
    )
    if company_id is not None:
        stmt = stmt.where(SsoContribution.company_id == company_id)
    if employee_id is not None:
        stmt = stmt.where(SsoContribution.employee_id == employee_id)
    return list((await session.execute(stmt)).scalars().all())


# ── PND filing ─────────────────────────────────────────────────────────


@router.post("/pnd-filings", response_model=PndFilingRead, status_code=201)
async def create_pnd_filing(
    body: PndFilingCreate, session: SessionDep, _user: CurrentUser
) -> PndFiling:
    filing = PndFiling(**body.model_dump(), state="draft")
    session.add(filing)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "filing already exists for this period") from exc
    return filing


@router.get("/pnd-filings", response_model=list[PndFilingRead])
async def list_pnd_filings(
    session: SessionDep,
    _user: CurrentUser,
    company_id: int | None = None,
    state: str | None = None,
) -> list[PndFiling]:
    stmt = (
        select(PndFiling)
        .where(PndFiling.deleted_at.is_(None))
        .options(selectinload(PndFiling.lines))
        .order_by(desc(PndFiling.period_year), desc(PndFiling.period_month))
    )
    if company_id is not None:
        stmt = stmt.where(PndFiling.company_id == company_id)
    if state is not None:
        stmt = stmt.where(PndFiling.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/pnd-filings/{filing_id}/calculate", response_model=PndFilingRead)
async def calculate_filing(
    filing_id: int, session: SessionDep, _user: CurrentUser
) -> PndFiling:
    stmt = (
        select(PndFiling)
        .where(PndFiling.id == filing_id)
        .options(selectinload(PndFiling.lines))
    )
    filing = (await session.execute(stmt)).scalar_one_or_none()
    if filing is None:
        raise HTTPException(404, "filing not found")
    return await calculate_pnd_filing(session, filing)


@router.post("/pnd-filings/{filing_id}/submit", response_model=PndFilingRead)
async def submit_filing(
    filing_id: int,
    session: SessionDep,
    user: CurrentUser,
    rd_receipt_number: str | None = None,
) -> PndFiling:
    stmt = (
        select(PndFiling)
        .where(PndFiling.id == filing_id)
        .options(selectinload(PndFiling.lines))
    )
    filing = (await session.execute(stmt)).scalar_one_or_none()
    if filing is None:
        raise HTTPException(404, "filing not found")
    return await submit_pnd_filing(session, filing, user.id, rd_receipt_number)


# ── Overtime ───────────────────────────────────────────────────────────


@router.post("/overtime-records", response_model=OvertimeRecordRead, status_code=201)
async def create_overtime(
    body: OvertimeRecordCreate, session: SessionDep, _user: CurrentUser
) -> OvertimeRecord:
    total, multiplier = compute_overtime(
        body.ot_kind, body.hours, body.base_hourly_rate
    )
    record = OvertimeRecord(
        **body.model_dump(),
        rate_multiplier=multiplier,
        total_amount=total,
        state="draft",
    )
    session.add(record)
    await session.flush()
    return record


@router.get("/overtime-records", response_model=list[OvertimeRecordRead])
async def list_overtime(
    session: SessionDep,
    _user: CurrentUser,
    employee_id: int | None = None,
    state: str | None = None,
) -> list[OvertimeRecord]:
    stmt = select(OvertimeRecord).order_by(desc(OvertimeRecord.work_date))
    if employee_id is not None:
        stmt = stmt.where(OvertimeRecord.employee_id == employee_id)
    if state is not None:
        stmt = stmt.where(OvertimeRecord.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/overtime-records/calc", response_model=OvertimeCalcResult)
async def calc_overtime(
    body: OvertimeCalcRequest, _user: CurrentUser
) -> OvertimeCalcResult:
    total, multiplier = compute_overtime(
        body.ot_kind, body.hours, body.base_hourly_rate
    )
    return OvertimeCalcResult(
        ot_kind=body.ot_kind,
        hours=body.hours,
        base_hourly_rate=body.base_hourly_rate,
        rate_multiplier=multiplier,
        total_amount=total,
    )


# ── Leave entitlement ──────────────────────────────────────────────────


@router.post("/leave-entitlements", response_model=LeaveEntitlementRead, status_code=201)
async def create_leave_entitlement(
    body: LeaveEntitlementCreate, session: SessionDep, _user: CurrentUser
) -> LeaveEntitlement:
    payload = body.model_dump()
    payload["remaining_days"] = body.granted_days + body.carried_over
    le = LeaveEntitlement(**payload, used_days=0)
    session.add(le)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "entitlement already exists for this employee/year/type") from exc
    return le


@router.get("/leave-entitlements", response_model=list[LeaveEntitlementRead])
async def list_leave_entitlements(
    session: SessionDep,
    _user: CurrentUser,
    employee_id: int | None = None,
    year: int | None = None,
) -> list[LeaveEntitlement]:
    stmt = select(LeaveEntitlement).order_by(
        desc(LeaveEntitlement.year), LeaveEntitlement.employee_id
    )
    if employee_id is not None:
        stmt = stmt.where(LeaveEntitlement.employee_id == employee_id)
    if year is not None:
        stmt = stmt.where(LeaveEntitlement.year == year)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/leave-entitlements/accrue", response_model=LeaveAccrualResult)
async def accrue_leave(
    body: LeaveAccrualRequest, session: SessionDep, _user: CurrentUser
) -> LeaveAccrualResult:
    employee = await session.get(Employee, body.employee_id)
    if employee is None or employee.hire_date is None:
        raise HTTPException(404, "employee or hire_date missing")
    from datetime import date as _date
    asof = _date(body.year, 12, 31)
    yos = years_of_service(employee.hire_date, asof)
    granted, rule = resolve_leave_grant(yos)
    return LeaveAccrualResult(
        employee_id=body.employee_id,
        year=body.year,
        years_of_service=yos,
        granted_days=granted,
        rule_applied=rule,
    )


# ── Employee transfer ──────────────────────────────────────────────────


@router.post("/employee-transfers", response_model=EmployeeTransferRead, status_code=201)
async def create_employee_transfer(
    body: EmployeeTransferCreate, session: SessionDep, _user: CurrentUser
) -> EmployeeTransfer:
    transfer = EmployeeTransfer(**body.model_dump(), state="pending")
    session.add(transfer)
    await session.flush()
    return transfer


@router.get("/employee-transfers", response_model=list[EmployeeTransferRead])
async def list_employee_transfers(
    session: SessionDep,
    _user: CurrentUser,
    employee_id: int | None = None,
    state: str | None = None,
) -> list[EmployeeTransfer]:
    stmt = select(EmployeeTransfer).order_by(desc(EmployeeTransfer.effective_date))
    if employee_id is not None:
        stmt = stmt.where(EmployeeTransfer.employee_id == employee_id)
    if state is not None:
        stmt = stmt.where(EmployeeTransfer.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/employee-transfers/{transfer_id}/complete", response_model=EmployeeTransferRead)
async def complete_transfer(
    transfer_id: int, session: SessionDep, _user: CurrentUser
) -> EmployeeTransfer:
    transfer = await session.get(EmployeeTransfer, transfer_id)
    if transfer is None:
        raise HTTPException(404, "transfer not found")
    return await complete_employee_transfer(session, transfer)

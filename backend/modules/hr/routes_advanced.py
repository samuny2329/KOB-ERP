"""Advanced HR routes — contracts, appraisals, expenses, training, Thai SSO/PVD/tax/PND1."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.db import SessionDep
from backend.modules.hr.models import Employee, Payslip
from backend.modules.hr.models_advanced import (
    Appraisal,
    AppraisalLine,
    Contract,
    Expense,
    ExpenseLine,
    JobPosition,
    OvertimeRequest,
    ProvidentFund,
    ProvidentFundMember,
    ShiftRoster,
    ThaiPnd1Line,
    ThaiSsoRecord,
    TrainingCourse,
    TrainingEnrollment,
)
from backend.modules.hr.schemas_advanced import (
    AppraisalCreate,
    AppraisalRead,
    ApprovePayload,
    ContractCreate,
    ContractRead,
    ExpenseCreate,
    ExpenseRead,
    JobPositionCreate,
    JobPositionRead,
    OvertimeRequestCreate,
    OvertimeRequestRead,
    Pnd1GeneratePayload,
    Pnd1LineRead,
    ProvidentFundCreate,
    ProvidentFundRead,
    PvdResult,
    ShiftRosterCreate,
    ShiftRosterRead,
    ThaiSsoResult,
    ThaiTaxResult,
    TrainingCourseCreate,
    TrainingCourseRead,
    TrainingEnrollmentCreate,
    TrainingEnrollmentRead,
)
from backend.modules.hr.service import (
    approve_expense,
    approve_overtime,
    compute_monthly_wht,
    compute_progressive_tax,
    compute_provident_fund,
    compute_thai_sso,
    compute_payslip,
    generate_pnd1_lines,
)

router = APIRouter(prefix="/hr", tags=["hr-advanced"])


# ── Job Positions ──────────────────────────────────────────────────────


@router.post("/job-positions", response_model=JobPositionRead, status_code=status.HTTP_201_CREATED)
async def create_job_position(payload: JobPositionCreate, session: SessionDep):
    pos = JobPosition(**payload.model_dump())
    session.add(pos)
    await session.flush()
    return pos


@router.get("/job-positions", response_model=list[JobPositionRead])
async def list_job_positions(session: SessionDep, department_id: int | None = None):
    stmt = select(JobPosition).where(JobPosition.deleted_at.is_(None), JobPosition.active.is_(True))
    if department_id:
        stmt = stmt.where(JobPosition.department_id == department_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Contracts ──────────────────────────────────────────────────────────


@router.post("/contracts", response_model=ContractRead, status_code=status.HTTP_201_CREATED)
async def create_contract(payload: ContractCreate, session: SessionDep):
    contract = Contract(**payload.model_dump(), state="draft")
    session.add(contract)
    await session.flush()
    return contract


@router.get("/contracts", response_model=list[ContractRead])
async def list_contracts(session: SessionDep, employee_id: int | None = None):
    stmt = select(Contract).where(Contract.deleted_at.is_(None))
    if employee_id:
        stmt = stmt.where(Contract.employee_id == employee_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/contracts/{contract_id}/activate", response_model=ContractRead)
async def activate_contract(contract_id: int, session: SessionDep):
    contract = await session.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "contract not found")
    from backend.core.workflow import WorkflowError
    try:
        contract.transition("running")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.flush()
    return contract


# ── Appraisals ─────────────────────────────────────────────────────────


@router.post("/appraisals", response_model=AppraisalRead, status_code=status.HTTP_201_CREATED)
async def create_appraisal(payload: AppraisalCreate, session: SessionDep):
    appraisal = Appraisal(
        employee_id=payload.employee_id, manager_id=payload.manager_id,
        period=payload.period, state="draft", overall_score=0,
    )
    session.add(appraisal)
    await session.flush()
    for line in payload.lines:
        session.add(AppraisalLine(appraisal_id=appraisal.id, **line.model_dump()))
    await session.flush()
    await session.refresh(appraisal, ["lines"])
    return appraisal


@router.get("/appraisals", response_model=list[AppraisalRead])
async def list_appraisals(session: SessionDep, employee_id: int | None = None):
    stmt = select(Appraisal).where(Appraisal.deleted_at.is_(None)).options(selectinload(Appraisal.lines))
    if employee_id:
        stmt = stmt.where(Appraisal.employee_id == employee_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/appraisals/{appraisal_id}/confirm", response_model=AppraisalRead)
async def confirm_appraisal(appraisal_id: int, session: SessionDep):
    appraisal = await session.get(Appraisal, appraisal_id, options=[selectinload(Appraisal.lines)])
    if not appraisal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "appraisal not found")
    from backend.core.workflow import WorkflowError
    try:
        appraisal.transition("confirmed")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    # Auto-compute overall score (weighted average)
    lines = appraisal.lines
    if lines:
        total_weight = sum(l.weight for l in lines)
        appraisal.overall_score = round(
            sum(l.score * l.weight for l in lines) / total_weight if total_weight > 0 else 0, 2
        )
    await session.flush()
    return appraisal


@router.post("/appraisals/{appraisal_id}/done", response_model=AppraisalRead)
async def complete_appraisal(appraisal_id: int, session: SessionDep):
    appraisal = await session.get(Appraisal, appraisal_id, options=[selectinload(Appraisal.lines)])
    if not appraisal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "appraisal not found")
    from backend.core.workflow import WorkflowError
    try:
        appraisal.transition("done")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    appraisal.done_at = datetime.now(UTC)
    await session.flush()
    return appraisal


# ── Expenses ───────────────────────────────────────────────────────────


@router.post("/expenses", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreate, session: SessionDep):
    expense = Expense(
        employee_id=payload.employee_id, name=payload.name,
        expense_date=payload.expense_date, account_id=payload.account_id, state="draft",
    )
    session.add(expense)
    await session.flush()
    total = 0.0
    for line in payload.lines:
        session.add(ExpenseLine(expense_id=expense.id, **line.model_dump()))
        total += line.amount
    expense.total_amount = round(total, 2)
    await session.flush()
    await session.refresh(expense, ["lines"])
    return expense


@router.get("/expenses", response_model=list[ExpenseRead])
async def list_expenses(session: SessionDep, employee_id: int | None = None, state: str | None = None):
    stmt = select(Expense).where(Expense.deleted_at.is_(None)).options(selectinload(Expense.lines))
    if employee_id:
        stmt = stmt.where(Expense.employee_id == employee_id)
    if state:
        stmt = stmt.where(Expense.state == state)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/expenses/{expense_id}/submit", response_model=ExpenseRead)
async def submit_expense(expense_id: int, session: SessionDep):
    expense = await session.get(Expense, expense_id, options=[selectinload(Expense.lines)])
    if not expense:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "expense not found")
    from backend.core.workflow import WorkflowError
    try:
        expense.transition("submitted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.flush()
    return expense


@router.post("/expenses/{expense_id}/approve", response_model=ExpenseRead)
async def approve_expense_endpoint(expense_id: int, payload: ApprovePayload, session: SessionDep):
    expense = await session.get(Expense, expense_id, options=[selectinload(Expense.lines)])
    if not expense:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "expense not found")
    return await approve_expense(session, expense, payload.approver_id)


# ── Training ───────────────────────────────────────────────────────────


@router.post("/training/courses", response_model=TrainingCourseRead, status_code=status.HTTP_201_CREATED)
async def create_training_course(payload: TrainingCourseCreate, session: SessionDep):
    course = TrainingCourse(**payload.model_dump())
    session.add(course)
    await session.flush()
    return course


@router.get("/training/courses", response_model=list[TrainingCourseRead])
async def list_training_courses(session: SessionDep):
    result = await session.execute(select(TrainingCourse).where(TrainingCourse.deleted_at.is_(None), TrainingCourse.active.is_(True)))
    return result.scalars().all()


@router.post("/training/enroll", response_model=TrainingEnrollmentRead, status_code=status.HTTP_201_CREATED)
async def enroll_training(payload: TrainingEnrollmentCreate, session: SessionDep):
    enrollment = TrainingEnrollment(**payload.model_dump())
    session.add(enrollment)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "employee already enrolled in this course")
    return enrollment


@router.get("/training/enrollments", response_model=list[TrainingEnrollmentRead])
async def list_enrollments(session: SessionDep, employee_id: int | None = None, course_id: int | None = None):
    stmt = select(TrainingEnrollment).where(TrainingEnrollment.deleted_at.is_(None))
    if employee_id:
        stmt = stmt.where(TrainingEnrollment.employee_id == employee_id)
    if course_id:
        stmt = stmt.where(TrainingEnrollment.course_id == course_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Provident Fund ─────────────────────────────────────────────────────


@router.post("/provident-funds", response_model=ProvidentFundRead, status_code=status.HTTP_201_CREATED)
async def create_provident_fund(payload: ProvidentFundCreate, session: SessionDep):
    fund = ProvidentFund(**payload.model_dump())
    session.add(fund)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "fund_code already exists")
    return fund


@router.get("/provident-funds", response_model=list[ProvidentFundRead])
async def list_provident_funds(session: SessionDep):
    result = await session.execute(select(ProvidentFund).where(ProvidentFund.deleted_at.is_(None), ProvidentFund.active.is_(True)))
    return result.scalars().all()


# ── Thai SSO / Tax Calculators ─────────────────────────────────────────


@router.get("/thai/sso", response_model=ThaiSsoResult)
async def calc_sso(gross_income: float):
    return compute_thai_sso(gross_income)


@router.get("/thai/income-tax", response_model=ThaiTaxResult)
async def calc_income_tax(annual_income: float):
    return compute_progressive_tax(annual_income)


@router.get("/thai/pvd", response_model=PvdResult)
async def calc_pvd(gross_income: float, employee_rate_pct: float = 5.0, employer_rate_pct: float = 5.0):
    return compute_provident_fund(gross_income, employee_rate_pct, employer_rate_pct)


# ── Payslip Compute ────────────────────────────────────────────────────


@router.post("/payslips/{payslip_id}/compute")
async def compute_payslip_endpoint(payslip_id: int, session: SessionDep):
    payslip = await session.get(Payslip, payslip_id)
    if not payslip:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "payslip not found")
    await compute_payslip(session, payslip)
    return {
        "id": payslip.id,
        "net_salary": float(payslip.net_salary),
        "net_after_tax": float(payslip.net_after_tax),
        "sso_employee": float(payslip.sso_employee),
        "income_tax": float(payslip.income_tax),
    }


# ── PND1 ───────────────────────────────────────────────────────────────


@router.post("/thai/pnd1/generate", response_model=list[Pnd1LineRead])
async def generate_pnd1(payload: Pnd1GeneratePayload, session: SessionDep):
    return await generate_pnd1_lines(session, payload.company_id, payload.period_month, payload.period_year)


@router.get("/thai/pnd1", response_model=list[Pnd1LineRead])
async def list_pnd1_lines(session: SessionDep, period_month: int | None = None, period_year: int | None = None):
    stmt = select(ThaiPnd1Line).where(ThaiPnd1Line.deleted_at.is_(None))
    if period_month:
        stmt = stmt.where(ThaiPnd1Line.period_month == period_month)
    if period_year:
        stmt = stmt.where(ThaiPnd1Line.period_year == period_year)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Shift Roster ───────────────────────────────────────────────────────


@router.post("/shift-roster", response_model=ShiftRosterRead, status_code=status.HTTP_201_CREATED)
async def create_shift_roster(payload: ShiftRosterCreate, session: SessionDep):
    roster = ShiftRoster(**payload.model_dump())
    session.add(roster)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "roster already exists for this employee/date")
    return roster


@router.get("/shift-roster", response_model=list[ShiftRosterRead])
async def list_shift_roster(session: SessionDep, employee_id: int | None = None):
    stmt = select(ShiftRoster).where(ShiftRoster.deleted_at.is_(None))
    if employee_id:
        stmt = stmt.where(ShiftRoster.employee_id == employee_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# ── Overtime Requests ──────────────────────────────────────────────────


@router.post("/overtime", response_model=OvertimeRequestRead, status_code=status.HTTP_201_CREATED)
async def create_overtime_request(payload: OvertimeRequestCreate, session: SessionDep):
    ot = OvertimeRequest(**payload.model_dump(), state="draft")
    session.add(ot)
    await session.flush()
    return ot


@router.get("/overtime", response_model=list[OvertimeRequestRead])
async def list_overtime_requests(session: SessionDep, employee_id: int | None = None, state: str | None = None):
    stmt = select(OvertimeRequest).where(OvertimeRequest.deleted_at.is_(None))
    if employee_id:
        stmt = stmt.where(OvertimeRequest.employee_id == employee_id)
    if state:
        stmt = stmt.where(OvertimeRequest.state == state)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/overtime/{ot_id}/approve", response_model=OvertimeRequestRead)
async def approve_ot(ot_id: int, payload: ApprovePayload, session: SessionDep):
    ot = await session.get(OvertimeRequest, ot_id)
    if not ot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "overtime request not found")
    return await approve_overtime(session, ot, payload.approver_id)


@router.post("/overtime/{ot_id}/reject", response_model=OvertimeRequestRead)
async def reject_ot(ot_id: int, session: SessionDep):
    ot = await session.get(OvertimeRequest, ot_id)
    if not ot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "overtime request not found")
    from backend.core.workflow import WorkflowError
    try:
        ot.transition("rejected")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.flush()
    return ot

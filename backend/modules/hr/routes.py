"""HTTP routes for the HR module."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.hr.models import (
    Attendance,
    Department,
    Employee,
    Leave,
    LeaveType,
    Payslip,
    PayslipLine,
    SalaryRule,
    SalaryStructure,
)
from backend.modules.hr.schemas import (
    AttendanceCreate,
    AttendanceRead,
    DepartmentCreate,
    DepartmentRead,
    EmployeeCreate,
    EmployeeRead,
    LeaveCreate,
    LeaveRead,
    LeaveTypeCreate,
    LeaveTypeRead,
    PayslipCreate,
    PayslipRead,
    SalaryStructureCreate,
    SalaryStructureRead,
)

router = APIRouter(prefix="/hr", tags=["hr"])


# ── Departments ───────────────────────────────────────────────────────


@router.get("/departments", response_model=list[DepartmentRead])
async def list_departments(session: SessionDep, _user: CurrentUser) -> list[Department]:
    rows = (
        await session.execute(
            select(Department).where(Department.deleted_at.is_(None)).order_by(Department.code)
        )
    ).scalars().all()
    return list(rows)


@router.post("/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreate, session: SessionDep, _user: CurrentUser
) -> Department:
    dept = Department(**body.model_dump())
    session.add(dept)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "department code already exists") from exc
    return dept


# ── Employees ─────────────────────────────────────────────────────────


@router.get("/employees", response_model=list[EmployeeRead])
async def list_employees(
    session: SessionDep, _user: CurrentUser, department_id: int | None = None
) -> list[Employee]:
    stmt = select(Employee).where(Employee.deleted_at.is_(None)).order_by(Employee.employee_code)
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/employees", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
async def create_employee(
    body: EmployeeCreate, session: SessionDep, _user: CurrentUser
) -> Employee:
    emp = Employee(**body.model_dump())
    session.add(emp)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "employee code already exists") from exc
    return emp


@router.get("/employees/{emp_id}", response_model=EmployeeRead)
async def get_employee(emp_id: int, session: SessionDep, _user: CurrentUser) -> Employee:
    emp = await session.get(Employee, emp_id)
    if not emp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")
    return emp


# ── Attendance ────────────────────────────────────────────────────────


@router.get("/attendances", response_model=list[AttendanceRead])
async def list_attendances(
    session: SessionDep, _user: CurrentUser, employee_id: int | None = None
) -> list[Attendance]:
    stmt = (
        select(Attendance)
        .where(Attendance.deleted_at.is_(None))
        .order_by(Attendance.check_in.desc())
    )
    if employee_id:
        stmt = stmt.where(Attendance.employee_id == employee_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/attendances", response_model=AttendanceRead, status_code=status.HTTP_201_CREATED)
async def create_attendance(
    body: AttendanceCreate, session: SessionDep, _user: CurrentUser
) -> Attendance:
    data = body.model_dump()
    att = Attendance(**data)
    if att.check_out and att.check_in:
        delta = att.check_out - att.check_in
        att.worked_hours = round(delta.total_seconds() / 3600, 2)
    session.add(att)
    await session.flush()
    return att


# ── Leave types ───────────────────────────────────────────────────────


@router.get("/leave-types", response_model=list[LeaveTypeRead])
async def list_leave_types(session: SessionDep, _user: CurrentUser) -> list[LeaveType]:
    rows = (
        await session.execute(select(LeaveType).where(LeaveType.deleted_at.is_(None)))
    ).scalars().all()
    return list(rows)


@router.post("/leave-types", response_model=LeaveTypeRead, status_code=status.HTTP_201_CREATED)
async def create_leave_type(
    body: LeaveTypeCreate, session: SessionDep, _user: CurrentUser
) -> LeaveType:
    lt = LeaveType(**body.model_dump())
    session.add(lt)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "leave type code already exists") from exc
    return lt


# ── Leaves ────────────────────────────────────────────────────────────


@router.get("/leaves", response_model=list[LeaveRead])
async def list_leaves(
    session: SessionDep, _user: CurrentUser, employee_id: int | None = None
) -> list[Leave]:
    stmt = select(Leave).where(Leave.deleted_at.is_(None)).order_by(Leave.created_at.desc())
    if employee_id:
        stmt = stmt.where(Leave.employee_id == employee_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/leaves", response_model=LeaveRead, status_code=status.HTTP_201_CREATED)
async def create_leave(body: LeaveCreate, session: SessionDep, _user: CurrentUser) -> Leave:
    leave = Leave(**body.model_dump())
    session.add(leave)
    await session.flush()
    return leave


@router.post("/leaves/{leave_id}/approve", response_model=LeaveRead)
async def approve_leave(leave_id: int, session: SessionDep, user: CurrentUser) -> Leave:
    leave = await session.get(Leave, leave_id)
    if not leave:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "leave not found")
    if leave.state != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot approve leave in state {leave.state!r}")
    leave.state = "approved"
    leave.approved_by_id = user.id
    leave.approved_at = datetime.now(timezone.utc)
    await session.flush()
    return leave


@router.post("/leaves/{leave_id}/reject", response_model=LeaveRead)
async def reject_leave(leave_id: int, session: SessionDep, _user: CurrentUser) -> Leave:
    leave = await session.get(Leave, leave_id)
    if not leave:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "leave not found")
    if leave.state not in ("submitted", "draft"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot reject leave in state {leave.state!r}")
    leave.state = "rejected"
    await session.flush()
    return leave


# ── Salary structures ─────────────────────────────────────────────────


@router.get("/salary-structures", response_model=list[SalaryStructureRead])
async def list_salary_structures(session: SessionDep, _user: CurrentUser) -> list[SalaryStructure]:
    rows = (
        await session.execute(select(SalaryStructure).where(SalaryStructure.deleted_at.is_(None)))
    ).scalars().all()
    return list(rows)


@router.post(
    "/salary-structures", response_model=SalaryStructureRead, status_code=status.HTTP_201_CREATED
)
async def create_salary_structure(
    body: SalaryStructureCreate, session: SessionDep, _user: CurrentUser
) -> SalaryStructure:
    data = body.model_dump(exclude={"rules"})
    structure = SalaryStructure(**data)
    session.add(structure)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "structure code already exists") from exc
    for rd in body.rules:
        session.add(SalaryRule(structure_id=structure.id, **rd.model_dump()))
    await session.flush()
    return structure


# ── Payslips ──────────────────────────────────────────────────────────


@router.get("/payslips", response_model=list[PayslipRead])
async def list_payslips(
    session: SessionDep, _user: CurrentUser, employee_id: int | None = None
) -> list[Payslip]:
    stmt = (
        select(Payslip)
        .where(Payslip.deleted_at.is_(None))
        .options(selectinload(Payslip.lines))
        .order_by(Payslip.period_from.desc())
    )
    if employee_id:
        stmt = stmt.where(Payslip.employee_id == employee_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/payslips", response_model=PayslipRead, status_code=status.HTTP_201_CREATED)
async def create_payslip(body: PayslipCreate, session: SessionDep, _user: CurrentUser) -> Payslip:
    payslip = Payslip(**body.model_dump())
    payslip.net_salary = payslip.basic_salary + payslip.total_allowances - payslip.total_deductions
    session.add(payslip)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "payslip number already exists") from exc
    return payslip


@router.post("/payslips/{payslip_id}/confirm", response_model=PayslipRead)
async def confirm_payslip(payslip_id: int, session: SessionDep, _user: CurrentUser) -> Payslip:
    ps = await session.get(Payslip, payslip_id)
    if not ps:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "payslip not found")
    if ps.state != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot confirm payslip in state {ps.state!r}")
    ps.state = "confirmed"
    ps.net_salary = ps.basic_salary + ps.total_allowances - ps.total_deductions
    await session.flush()
    await session.refresh(ps, ["lines"])
    return ps


@router.post("/payslips/{payslip_id}/pay", response_model=PayslipRead)
async def mark_payslip_paid(
    payslip_id: int, session: SessionDep, _user: CurrentUser
) -> Payslip:
    ps = await session.get(Payslip, payslip_id)
    if not ps:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "payslip not found")
    if ps.state != "confirmed":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"cannot mark paid payslip in state {ps.state!r}"
        )
    ps.state = "paid"
    ps.paid_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(ps, ["lines"])
    return ps

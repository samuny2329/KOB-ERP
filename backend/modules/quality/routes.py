"""HTTP routes for the quality module."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.core.models_audit import append_activity
from backend.core.workflow import WorkflowError
from backend.modules.outbound.models import Order
from backend.modules.quality.models import DEFECT_SEVERITIES, Check, Defect
from backend.modules.quality.schemas import (
    CheckCreate,
    CheckRead,
    DefectCreate,
    DefectRead,
)

router = APIRouter(prefix="/quality", tags=["quality"])


@router.post("/checks", response_model=CheckRead, status_code=status.HTTP_201_CREATED)
async def create_check(body: CheckCreate, session: SessionDep, user: CurrentUser) -> Check:
    if (await session.get(Order, body.order_id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")
    check = Check(**body.model_dump(), state="pending")
    session.add(check)
    await session.flush()
    await append_activity(
        session, actor_id=user.id, action="quality.check.created",
        ref=str(body.order_id), code=str(check.id),
    )
    return check


@router.get("/checks", response_model=list[CheckRead])
async def list_checks(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
    order_id: int | None = None,
) -> list[Check]:
    stmt = (
        select(Check)
        .where(Check.deleted_at.is_(None))
        .options(selectinload(Check.defects))
        .order_by(Check.id.desc())
    )
    if state is not None:
        stmt = stmt.where(Check.state == state)
    if order_id is not None:
        stmt = stmt.where(Check.order_id == order_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/checks/{check_id}/transition", response_model=CheckRead)
async def transition_check(
    check_id: int, target: str, session: SessionDep, user: CurrentUser
) -> Check:
    check = await session.get(Check, check_id)
    if check is None or check.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "check not found")
    try:
        check.transition(target)
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    check.checked_by_id = user.id
    check.checked_at = datetime.now(UTC)
    await append_activity(
        session, actor_id=user.id, action=f"quality.check.{target}",
        ref=str(check.order_id), code=str(check.id),
    )
    return check


@router.post("/defects", response_model=DefectRead, status_code=status.HTTP_201_CREATED)
async def create_defect(
    body: DefectCreate, session: SessionDep, user: CurrentUser
) -> Defect:
    if body.severity not in DEFECT_SEVERITIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid severity: {body.severity}")
    if (await session.get(Check, body.check_id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "quality check not found")
    defect = Defect(**body.model_dump(), occurred_at=datetime.now(UTC))
    session.add(defect)
    await session.flush()
    await append_activity(
        session, actor_id=user.id, action="quality.defect.recorded",
        ref=str(body.check_id), code=defect.defect_type,
        note=f"{body.severity}: {body.defect_type}",
    )
    return defect


@router.get("/defects", response_model=list[DefectRead])
async def list_defects(
    session: SessionDep, _user: CurrentUser, check_id: int | None = None
) -> list[Defect]:
    stmt = select(Defect).order_by(Defect.id.desc())
    if check_id is not None:
        stmt = stmt.where(Defect.check_id == check_id)
    return list((await session.execute(stmt)).scalars().all())

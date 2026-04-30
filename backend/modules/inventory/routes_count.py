"""Routes for the cycle-count workflow."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.core.models_audit import append_activity
from backend.core.workflow import WorkflowError
from backend.modules.inventory.models_count import (
    CountAdjustment,
    CountEntry,
    CountSession,
    CountTask,
)
from backend.modules.inventory.schemas_count import (
    CountAdjustmentRead,
    CountEntryCreate,
    CountEntryRead,
    CountSessionCreate,
    CountSessionRead,
    CountTaskCreate,
    CountTaskRead,
)

router = APIRouter(prefix="/inventory/counts", tags=["counts"])


# ── Session ────────────────────────────────────────────────────────────


@router.post("/sessions", response_model=CountSessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CountSessionCreate, session: SessionDep, user: CurrentUser
) -> CountSession:
    cs = CountSession(**body.model_dump(), state="draft")
    session.add(cs)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "session name already exists") from exc
    await append_activity(
        session, actor_id=user.id, action="count.session.created",
        ref=cs.name, code=str(cs.id),
    )
    return cs


@router.get("/sessions", response_model=list[CountSessionRead])
async def list_sessions(
    session: SessionDep, _user: CurrentUser, state: str | None = None
) -> list[CountSession]:
    stmt = select(CountSession).where(CountSession.deleted_at.is_(None)).order_by(
        CountSession.id.desc()
    )
    if state is not None:
        stmt = stmt.where(CountSession.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/sessions/{session_id}/transition", response_model=CountSessionRead)
async def transition_session(
    session_id: int, target: str, session: SessionDep, user: CurrentUser
) -> CountSession:
    cs = await session.get(CountSession, session_id)
    if cs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "count session not found")
    try:
        cs.transition(target)
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await append_activity(
        session, actor_id=user.id, action=f"count.session.{target}",
        ref=cs.name, code=str(cs.id),
    )
    return cs


# ── Task ───────────────────────────────────────────────────────────────


@router.post("/tasks", response_model=CountTaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: CountTaskCreate, session: SessionDep, _user: CurrentUser
) -> CountTask:
    if (await session.get(CountSession, body.session_id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "count session not found")
    task = CountTask(**body.model_dump(), state="assigned")
    session.add(task)
    await session.flush()
    return task


@router.get("/tasks", response_model=list[CountTaskRead])
async def list_tasks(
    session: SessionDep, _user: CurrentUser, session_id: int | None = None
) -> list[CountTask]:
    stmt = (
        select(CountTask)
        .where(CountTask.deleted_at.is_(None))
        .options(selectinload(CountTask.entries))
        .order_by(CountTask.id.desc())
    )
    if session_id is not None:
        stmt = stmt.where(CountTask.session_id == session_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/tasks/{task_id}/transition", response_model=CountTaskRead)
async def transition_task(
    task_id: int, target: str, session: SessionDep, user: CurrentUser
) -> CountTask:
    task = await session.get(CountTask, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "count task not found")
    try:
        task.transition(target)
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if target == "verified":
        task.verified_by = user.id
        task.verified_at = datetime.now(UTC)
    await append_activity(
        session, actor_id=user.id, action=f"count.task.{target}",
        ref=str(task.id), code=str(task.session_id),
    )
    return task


# ── Entries ────────────────────────────────────────────────────────────


@router.post("/entries", response_model=CountEntryRead, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: CountEntryCreate, session: SessionDep, user: CurrentUser
) -> CountEntry:
    task = await session.get(CountTask, body.task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "count task not found")
    if task.state == "assigned":
        # First scan auto-flips the task to "counting".
        task.transition("counting")
    elif task.state not in {"counting", "submitted"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"can't add entries while task is {task.state!r}"
        )
    entry = CountEntry(
        task_id=body.task_id,
        product_id=body.product_id,
        lot_id=body.lot_id,
        qty=body.qty,
        user_id=user.id,
        scanned_at=datetime.now(UTC),
    )
    session.add(entry)
    await session.flush()
    return entry


@router.get("/entries", response_model=list[CountEntryRead])
async def list_entries(
    session: SessionDep, _user: CurrentUser, task_id: int | None = None
) -> list[CountEntry]:
    stmt = select(CountEntry).order_by(CountEntry.id.desc())
    if task_id is not None:
        stmt = stmt.where(CountEntry.task_id == task_id)
    return list((await session.execute(stmt)).scalars().all())


# ── Adjustments ────────────────────────────────────────────────────────


@router.get("/adjustments", response_model=list[CountAdjustmentRead])
async def list_adjustments(
    session: SessionDep,
    _user: CurrentUser,
    session_id: int | None = None,
    state: str | None = None,
) -> list[CountAdjustment]:
    stmt = select(CountAdjustment).order_by(CountAdjustment.id.desc())
    if session_id is not None:
        stmt = stmt.where(CountAdjustment.session_id == session_id)
    if state is not None:
        stmt = stmt.where(CountAdjustment.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/adjustments/{adj_id}/approve", response_model=CountAdjustmentRead)
async def approve_adjustment(
    adj_id: int, session: SessionDep, user: CurrentUser
) -> CountAdjustment:
    adj = await session.get(CountAdjustment, adj_id)
    if adj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "adjustment not found")
    if adj.state != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "only pending adjustments can be approved")
    adj.state = "approved"
    adj.approved_by = user.id
    adj.approved_at = datetime.now(UTC)
    await append_activity(
        session, actor_id=user.id, action="count.adjustment.approved",
        ref=str(adj.id), code=str(adj.session_id),
    )
    return adj

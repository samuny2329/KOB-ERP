"""HTTP routes for the manufacturing module."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.mfg.models import (
    BomLine,
    BomTemplate,
    ManufacturingOrder,
    SubconRecon,
    SubconReconLine,
    WorkOrder,
)
from backend.modules.mfg.schemas import (
    BomCreate,
    BomRead,
    MoCreate,
    MoRead,
    SubconReconCreate,
    SubconReconRead,
    WorkOrderCreate,
    WorkOrderRead,
)

router = APIRouter(prefix="/mfg", tags=["manufacturing"])


# ── BoM ───────────────────────────────────────────────────────────────


@router.get("/boms", response_model=list[BomRead])
async def list_boms(session: SessionDep, _user: CurrentUser) -> list[BomTemplate]:
    rows = (
        await session.execute(
            select(BomTemplate)
            .where(BomTemplate.deleted_at.is_(None))
            .options(selectinload(BomTemplate.lines))
        )
    ).scalars().all()
    return list(rows)


@router.post("/boms", response_model=BomRead, status_code=status.HTTP_201_CREATED)
async def create_bom(body: BomCreate, session: SessionDep, _user: CurrentUser) -> BomTemplate:
    data = body.model_dump(exclude={"lines"})
    bom = BomTemplate(**data)
    session.add(bom)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "BoM code already exists") from exc
    for ld in body.lines:
        session.add(BomLine(bom_id=bom.id, **ld.model_dump()))
    await session.flush()
    await session.refresh(bom, ["lines"])
    return bom


# ── Manufacturing Orders ───────────────────────────────────────────────


@router.get("/orders", response_model=list[MoRead])
async def list_mos(
    session: SessionDep, _user: CurrentUser, state: str | None = None
) -> list[ManufacturingOrder]:
    stmt = select(ManufacturingOrder).where(ManufacturingOrder.deleted_at.is_(None))
    if state:
        stmt = stmt.where(ManufacturingOrder.state == state)
    return list((await session.execute(stmt.order_by(ManufacturingOrder.created_at.desc()))).scalars().all())


@router.post("/orders", response_model=MoRead, status_code=status.HTTP_201_CREATED)
async def create_mo(body: MoCreate, session: SessionDep, _user: CurrentUser) -> ManufacturingOrder:
    mo = ManufacturingOrder(**body.model_dump())
    session.add(mo)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "MO number already exists") from exc
    return mo


@router.post("/orders/{mo_id}/transition", response_model=MoRead)
async def transition_mo(
    mo_id: int, new_state: str, session: SessionDep, _user: CurrentUser
) -> ManufacturingOrder:
    TRANSITIONS = {
        "draft": ["confirmed", "cancelled"],
        "confirmed": ["in_progress", "cancelled"],
        "in_progress": ["done", "cancelled"],
    }
    mo = await session.get(ManufacturingOrder, mo_id)
    if not mo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MO not found")
    allowed = TRANSITIONS.get(mo.state, [])
    if new_state not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot transition from {mo.state!r} to {new_state!r}",
        )
    mo.state = new_state
    if new_state == "in_progress":
        mo.started_at = datetime.now(timezone.utc)
    elif new_state == "done":
        mo.completed_at = datetime.now(timezone.utc)
    await session.flush()
    return mo


# ── Work Orders ────────────────────────────────────────────────────────


@router.get("/work-orders", response_model=list[WorkOrderRead])
async def list_work_orders(
    session: SessionDep, _user: CurrentUser, mo_id: int | None = None
) -> list[WorkOrder]:
    stmt = select(WorkOrder).where(WorkOrder.deleted_at.is_(None))
    if mo_id:
        stmt = stmt.where(WorkOrder.mo_id == mo_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/work-orders", response_model=WorkOrderRead, status_code=status.HTTP_201_CREATED)
async def create_work_order(
    body: WorkOrderCreate, session: SessionDep, _user: CurrentUser
) -> WorkOrder:
    wo = WorkOrder(**body.model_dump())
    session.add(wo)
    await session.flush()
    return wo


# ── Subcon recon ──────────────────────────────────────────────────────


@router.get("/subcon-recons", response_model=list[SubconReconRead])
async def list_subcon_recons(
    session: SessionDep, _user: CurrentUser
) -> list[SubconRecon]:
    rows = (
        await session.execute(
            select(SubconRecon).where(SubconRecon.deleted_at.is_(None)).order_by(SubconRecon.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


@router.post("/subcon-recons", response_model=SubconReconRead, status_code=status.HTTP_201_CREATED)
async def create_subcon_recon(
    body: SubconReconCreate, session: SessionDep, _user: CurrentUser
) -> SubconRecon:
    data = body.model_dump(exclude={"lines"})
    recon = SubconRecon(**data)
    session.add(recon)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "recon number already exists") from exc
    for ld in body.lines:
        session.add(SubconReconLine(recon_id=recon.id, **ld.model_dump()))
    await session.flush()
    return recon

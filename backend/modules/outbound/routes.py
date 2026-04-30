"""HTTP routes for the outbound + courier-master + activity-log modules."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.core.models_audit import ActivityLog, verify_chain
from backend.modules.outbound.models import DispatchBatch, Order
from backend.modules.outbound.schemas import (
    ActivityLogRead,
    CourierCreate,
    CourierRead,
    DispatchBatchCreate,
    DispatchBatchRead,
    OrderCreate,
    OrderRead,
    PickfaceCreate,
    PickfaceRead,
    RackCreate,
    RackRead,
    ScanItemCreate,
    ScanItemRead,
)
from backend.modules.outbound.service import (
    add_scan,
    create_dispatch_batch,
    create_order_with_lines,
    transition_batch,
    transition_order,
)
from backend.modules.wms.models_outbound import Courier, Pickface, Rack

router = APIRouter(tags=["outbound"])


# ── Master data: Rack / Pickface / Courier ────────────────────────────


@router.post("/wms/racks", response_model=RackRead, status_code=status.HTTP_201_CREATED)
async def create_rack(body: RackCreate, session: SessionDep, _user: CurrentUser) -> Rack:
    rack = Rack(**body.model_dump(), active=True)
    session.add(rack)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "rack code already exists in zone") from exc
    return rack


@router.get("/wms/racks", response_model=list[RackRead])
async def list_racks(
    session: SessionDep,
    _user: CurrentUser,
    zone_id: int | None = None,
) -> list[Rack]:
    stmt = select(Rack).where(Rack.deleted_at.is_(None))
    if zone_id is not None:
        stmt = stmt.where(Rack.zone_id == zone_id)
    return list((await session.execute(stmt.order_by(Rack.code))).scalars().all())


@router.post("/wms/pickfaces", response_model=PickfaceRead, status_code=status.HTTP_201_CREATED)
async def create_pickface(
    body: PickfaceCreate, session: SessionDep, _user: CurrentUser
) -> Pickface:
    pf = Pickface(**body.model_dump(), active=True)
    session.add(pf)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "pickface code already exists in zone") from exc
    return pf


@router.get("/wms/pickfaces", response_model=list[PickfaceRead])
async def list_pickfaces(
    session: SessionDep,
    _user: CurrentUser,
    zone_id: int | None = None,
) -> list[Pickface]:
    stmt = select(Pickface).where(Pickface.deleted_at.is_(None))
    if zone_id is not None:
        stmt = stmt.where(Pickface.zone_id == zone_id)
    return list((await session.execute(stmt.order_by(Pickface.code))).scalars().all())


@router.post("/wms/couriers", response_model=CourierRead, status_code=status.HTTP_201_CREATED)
async def create_courier(
    body: CourierCreate, session: SessionDep, _user: CurrentUser
) -> Courier:
    courier = Courier(**body.model_dump(), active=True)
    session.add(courier)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "courier code already exists") from exc
    return courier


@router.get("/wms/couriers", response_model=list[CourierRead])
async def list_couriers(session: SessionDep, _user: CurrentUser) -> list[Courier]:
    return list(
        (
            await session.execute(
                select(Courier)
                .where(Courier.deleted_at.is_(None))
                .order_by(Courier.sequence, Courier.code)
            )
        )
        .scalars()
        .all()
    )


# ── Outbound orders ────────────────────────────────────────────────────


@router.post("/outbound/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(body: OrderCreate, session: SessionDep, user: CurrentUser) -> Order:
    if (
        await session.execute(select(Order).where(Order.ref == body.ref))
    ).scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "order ref already exists")

    return await create_order_with_lines(
        session,
        ref=body.ref,
        customer_name=body.customer_name,
        platform=body.platform,
        courier_id=body.courier_id,
        note=body.note,
        lines_data=[ln.model_dump() for ln in body.lines],
        actor_id=user.id,
    )


@router.get("/outbound/orders", response_model=list[OrderRead])
async def list_orders(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.deleted_at.is_(None))
        .options(selectinload(Order.lines))
        .order_by(Order.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if state is not None:
        stmt = stmt.where(Order.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/outbound/orders/{order_id}", response_model=OrderRead)
async def get_order(order_id: int, session: SessionDep, _user: CurrentUser) -> Order:
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.lines))
    )
    order = (await session.execute(stmt)).scalar_one_or_none()
    if order is None or order.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")
    return order


@router.post("/outbound/orders/{order_id}/transition", response_model=OrderRead)
async def post_transition_order(
    order_id: int,
    target: str,
    session: SessionDep,
    user: CurrentUser,
) -> Order:
    order = await get_order(order_id, session, user)
    return await transition_order(session, order, target, actor_id=user.id)


# ── Dispatch batches ───────────────────────────────────────────────────


@router.post(
    "/outbound/dispatch-batches",
    response_model=DispatchBatchRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch(
    body: DispatchBatchCreate, session: SessionDep, user: CurrentUser
) -> DispatchBatch:
    return await create_dispatch_batch(
        session,
        courier_id=body.courier_id,
        work_date=body.work_date,
        note=body.note,
        actor_id=user.id,
    )


@router.get("/outbound/dispatch-batches", response_model=list[DispatchBatchRead])
async def list_batches(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
) -> list[DispatchBatch]:
    stmt = (
        select(DispatchBatch)
        .where(DispatchBatch.deleted_at.is_(None))
        .options(selectinload(DispatchBatch.scans))
        .order_by(DispatchBatch.id.desc())
    )
    if state is not None:
        stmt = stmt.where(DispatchBatch.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/outbound/dispatch-batches/{batch_id}", response_model=DispatchBatchRead)
async def get_batch(
    batch_id: int, session: SessionDep, _user: CurrentUser
) -> DispatchBatch:
    stmt = (
        select(DispatchBatch)
        .where(DispatchBatch.id == batch_id)
        .options(selectinload(DispatchBatch.scans))
    )
    batch = (await session.execute(stmt)).scalar_one_or_none()
    if batch is None or batch.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dispatch batch not found")
    return batch


@router.post(
    "/outbound/dispatch-batches/{batch_id}/scan",
    response_model=ScanItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def scan_into_batch(
    batch_id: int, body: ScanItemCreate, session: SessionDep, user: CurrentUser
):
    batch = await get_batch(batch_id, session, user)
    return await add_scan(
        session,
        batch=batch,
        barcode=body.barcode,
        order_id=body.order_id,
        actor_id=user.id,
    )


@router.post(
    "/outbound/dispatch-batches/{batch_id}/transition", response_model=DispatchBatchRead
)
async def post_transition_batch(
    batch_id: int, target: str, session: SessionDep, user: CurrentUser
) -> DispatchBatch:
    batch = await get_batch(batch_id, session, user)
    return await transition_batch(session, batch, target, actor_id=user.id)


# ── Activity log ───────────────────────────────────────────────────────


@router.get("/audit/activity-log", response_model=list[ActivityLogRead])
async def list_activity(
    session: SessionDep,
    _user: CurrentUser,
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
) -> list[ActivityLog]:
    stmt = select(ActivityLog).order_by(desc(ActivityLog.id)).limit(limit).offset(offset)
    if action is not None:
        stmt = stmt.where(ActivityLog.action == action)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/audit/activity-log/verify")
async def verify_activity_chain(
    session: SessionDep, _user: CurrentUser
) -> dict[str, object]:
    ok, broken_id = await verify_chain(session)
    return {"valid": ok, "broken_at_id": broken_id}

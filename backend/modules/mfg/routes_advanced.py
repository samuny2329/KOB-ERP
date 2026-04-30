"""Advanced manufacturing routes — work centers, routing, scrap, unbuild, OEE, signals."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.mfg.models import ManufacturingOrder, SubconVendor
from backend.modules.mfg.models_advanced import (
    BatchConsolidation,
    BatchConsolidationItem,
    MoComponentLine,
    MoProductionSignal,
    MoScrap,
    ProductionShift,
    Routing,
    RoutingOperation,
    UnbuildOrder,
    WorkCenter,
    WorkCenterOee,
)
from backend.modules.mfg.service import (
    close_mo,
    complete_mo,
    compute_oee,
    compute_production_signal,
    confirm_mo,
    propose_batch_consolidation,
    record_scrap,
    recompute_subcon_quality,
    start_mo,
    validate_unbuild,
)
from backend.modules.mfg.schemas import MoRead

router = APIRouter(prefix="/mfg", tags=["mfg-advanced"])


# ── Work Centers ───────────────────────────────────────────────────────


@router.post("/work-centers", status_code=status.HTTP_201_CREATED)
async def create_work_center(
    body: dict, session: SessionDep, _user: CurrentUser
) -> dict:
    wc = WorkCenter(**body)
    session.add(wc)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "work center code already exists") from exc
    return {"id": wc.id, "code": wc.code, "name": wc.name, "capacity": wc.capacity,
            "cost_per_hour": float(wc.cost_per_hour), "oee_target": wc.oee_target}


@router.get("/work-centers")
async def list_work_centers(session: SessionDep, _user: CurrentUser) -> list[dict]:
    rows = list(
        (await session.execute(
            select(WorkCenter).where(WorkCenter.deleted_at.is_(None), WorkCenter.active.is_(True))
            .order_by(WorkCenter.code)
        )).scalars().all()
    )
    return [{"id": r.id, "code": r.code, "name": r.name, "capacity": r.capacity,
             "cost_per_hour": float(r.cost_per_hour), "oee_target": r.oee_target} for r in rows]


# ── Routings ───────────────────────────────────────────────────────────


@router.post("/routings", status_code=status.HTTP_201_CREATED)
async def create_routing(body: dict, session: SessionDep, _user: CurrentUser) -> dict:
    ops = body.pop("operations", [])
    routing = Routing(**body)
    session.add(routing)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "routing code already exists") from exc
    for op_data in ops:
        session.add(RoutingOperation(routing_id=routing.id, **op_data))
    await session.flush()
    await session.refresh(routing, ["operations"])
    return {"id": routing.id, "code": routing.code, "name": routing.name,
            "operations": [{"id": o.id, "sequence": o.sequence, "name": o.name,
                            "work_center_id": o.work_center_id,
                            "default_duration": o.default_duration} for o in routing.operations]}


@router.get("/routings")
async def list_routings(session: SessionDep, _user: CurrentUser) -> list[dict]:
    rows = list(
        (await session.execute(
            select(Routing)
            .where(Routing.deleted_at.is_(None), Routing.active.is_(True))
            .options(selectinload(Routing.operations))
        )).scalars().all()
    )
    return [{"id": r.id, "code": r.code, "name": r.name,
             "operation_count": len(r.operations)} for r in rows]


# ── MO Workflow (enhanced) ─────────────────────────────────────────────


@router.post("/orders/{mo_id}/confirm")
async def confirm_mo_route(mo_id: int, session: SessionDep, _user: CurrentUser) -> dict:
    mo = await session.get(ManufacturingOrder, mo_id, options=[selectinload(ManufacturingOrder.work_orders)])
    if mo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MO not found")
    mo = await confirm_mo(session, mo)
    return {"id": mo.id, "state": mo.state, "number": mo.number}


@router.post("/orders/{mo_id}/start")
async def start_mo_route(mo_id: int, session: SessionDep, _user: CurrentUser) -> dict:
    mo = await session.get(ManufacturingOrder, mo_id)
    if mo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MO not found")
    mo = await start_mo(session, mo)
    return {"id": mo.id, "state": mo.state, "started_at": mo.started_at}


@router.post("/orders/{mo_id}/close")
async def close_mo_route(mo_id: int, session: SessionDep, _user: CurrentUser) -> dict:
    mo = await session.get(ManufacturingOrder, mo_id)
    if mo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MO not found")
    mo = await close_mo(session, mo)
    return {"id": mo.id, "state": mo.state,
            "material_cost": float(mo.material_cost),
            "labor_cost": float(mo.labor_cost),
            "total_cost": float(mo.total_cost)}


@router.post("/orders/{mo_id}/done")
async def complete_mo_route(mo_id: int, session: SessionDep, _user: CurrentUser) -> dict:
    mo = await session.get(ManufacturingOrder, mo_id)
    if mo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MO not found")
    mo = await complete_mo(session, mo)
    return {"id": mo.id, "state": mo.state, "completed_at": mo.completed_at}


# ── Component Lines ────────────────────────────────────────────────────


@router.get("/orders/{mo_id}/components")
async def list_mo_components(mo_id: int, session: SessionDep, _user: CurrentUser) -> list[dict]:
    rows = list(
        (await session.execute(
            select(MoComponentLine).where(MoComponentLine.mo_id == mo_id)
        )).scalars().all()
    )
    return [{"id": r.id, "product_id": r.product_id, "lot_id": r.lot_id,
             "qty_demand": float(r.qty_demand), "qty_done": float(r.qty_done),
             "unit_cost": float(r.unit_cost)} for r in rows]


@router.put("/orders/{mo_id}/components/{line_id}")
async def update_component_line(
    mo_id: int, line_id: int,
    qty_done: float, lot_id: int | None = None, unit_cost: float = 0.0,
    session: SessionDep = None, _user: CurrentUser = None,
) -> dict:
    line = await session.get(MoComponentLine, line_id)
    if line is None or line.mo_id != mo_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "component line not found")
    line.qty_done = qty_done
    if lot_id is not None:
        line.lot_id = lot_id
    line.unit_cost = unit_cost
    line.total_cost = round(qty_done * unit_cost, 2)
    await session.flush()
    return {"id": line.id, "qty_done": float(line.qty_done), "total_cost": float(line.total_cost)}


# ── Scrap During Production ────────────────────────────────────────────


@router.post("/orders/{mo_id}/scrap")
async def scrap_during_production(
    mo_id: int,
    product_id: int,
    qty: float,
    session: SessionDep,
    _user: CurrentUser,
    reason: str | None = None,
    lot_id: int | None = None,
    unit_cost: float = 0.0,
) -> dict:
    mo = await session.get(ManufacturingOrder, mo_id)
    if mo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MO not found")
    scrap = await record_scrap(session, mo, product_id, qty, reason, lot_id, unit_cost)
    return {"id": scrap.id, "qty": float(scrap.qty), "total_cost": float(scrap.total_cost)}


@router.get("/orders/{mo_id}/scraps")
async def list_mo_scraps(mo_id: int, session: SessionDep, _user: CurrentUser) -> list[dict]:
    rows = list(
        (await session.execute(
            select(MoScrap).where(MoScrap.mo_id == mo_id)
        )).scalars().all()
    )
    return [{"id": r.id, "product_id": r.product_id, "lot_id": r.lot_id,
             "qty": float(r.qty), "scrap_reason": r.scrap_reason,
             "total_cost": float(r.total_cost)} for r in rows]


# ── Unbuild Orders ─────────────────────────────────────────────────────


@router.post("/unbuilds", status_code=status.HTTP_201_CREATED)
async def create_unbuild(body: dict, session: SessionDep, _user: CurrentUser) -> dict:
    count = len(list(
        (await session.execute(select(UnbuildOrder).where(UnbuildOrder.deleted_at.is_(None)))).scalars().all()
    ))
    name = f"UB/{count + 1:06d}"
    unbuild = UnbuildOrder(name=name, **body)
    session.add(unbuild)
    await session.flush()
    return {"id": unbuild.id, "name": unbuild.name, "state": unbuild.state}


@router.post("/unbuilds/{unbuild_id}/validate")
async def validate_unbuild_route(unbuild_id: int, session: SessionDep, _user: CurrentUser) -> dict:
    unbuild = await session.get(UnbuildOrder, unbuild_id)
    if unbuild is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unbuild order not found")
    unbuild = await validate_unbuild(session, unbuild)
    return {"id": unbuild.id, "state": unbuild.state, "done_at": unbuild.done_at}


# ── Production Shifts ──────────────────────────────────────────────────


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
async def create_shift(body: dict, session: SessionDep, _user: CurrentUser) -> dict:
    shift = ProductionShift(**body)
    session.add(shift)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "shift code already exists for this warehouse") from exc
    return {"id": shift.id, "code": shift.code, "name": shift.name,
            "start_hour": shift.start_hour, "end_hour": shift.end_hour}


@router.get("/shifts")
async def list_shifts(
    session: SessionDep, _user: CurrentUser, warehouse_id: int | None = None
) -> list[dict]:
    stmt = select(ProductionShift).where(ProductionShift.deleted_at.is_(None), ProductionShift.active.is_(True))
    if warehouse_id is not None:
        stmt = stmt.where(ProductionShift.warehouse_id == warehouse_id)
    rows = list((await session.execute(stmt)).scalars().all())
    return [{"id": r.id, "code": r.code, "name": r.name,
             "start_hour": r.start_hour, "end_hour": r.end_hour} for r in rows]


# ── OEE ────────────────────────────────────────────────────────────────


@router.post("/work-centers/{wc_id}/oee", status_code=status.HTTP_201_CREATED)
async def record_oee(
    wc_id: int,
    planned_time: int,
    available_time: int,
    run_time: int,
    ideal_cycle_time: float,
    total_units: int,
    good_units: int,
    session: SessionDep,
    _user: CurrentUser,
    oee_date: date = None,
    shift_id: int | None = None,
) -> dict:
    if oee_date is None:
        oee_date = date.today()
    metrics = compute_oee(planned_time, available_time, run_time, ideal_cycle_time, total_units, good_units)
    oee = WorkCenterOee(
        work_center_id=wc_id,
        shift_id=shift_id,
        oee_date=oee_date,
        planned_time=planned_time,
        available_time=available_time,
        run_time=run_time,
        ideal_cycle_time=ideal_cycle_time,
        total_units=total_units,
        good_units=good_units,
        **metrics,
    )
    session.add(oee)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "OEE record already exists for this date/shift") from exc
    return {"id": oee.id, **metrics}


@router.get("/work-centers/{wc_id}/oee")
async def get_oee_history(
    wc_id: int, session: SessionDep, _user: CurrentUser, limit: int = 30
) -> list[dict]:
    rows = list(
        (await session.execute(
            select(WorkCenterOee)
            .where(WorkCenterOee.work_center_id == wc_id)
            .order_by(WorkCenterOee.oee_date.desc())
            .limit(limit)
        )).scalars().all()
    )
    return [{"id": r.id, "oee_date": r.oee_date, "oee": r.oee,
             "availability": r.availability, "performance": r.performance,
             "quality": r.quality, "good_units": r.good_units} for r in rows]


# ── Subcon Quality ─────────────────────────────────────────────────────


@router.post("/subcon-vendors/{vendor_id}/quality/recompute")
async def recompute_quality(vendor_id: int, session: SessionDep, _user: CurrentUser) -> dict:
    sv = await recompute_subcon_quality(session, vendor_id)
    return {"id": sv.id, "variance_rate": sv.variance_rate, "quality_score": sv.quality_score}


# ── Production Signals (KOB-exclusive) ────────────────────────────────


@router.post("/production-signals/compute")
async def compute_signal(
    product_id: int,
    current_stock: float,
    wip_qty: float,
    session: SessionDep,
    _user: CurrentUser,
    lookback_days: int = 30,
) -> dict:
    signal = await compute_production_signal(
        session, product_id, current_stock, wip_qty, lookback_days=lookback_days
    )
    return {"id": signal.id, "suggested_qty": signal.suggested_qty,
            "avg_daily_demand": signal.avg_daily_demand, "status": signal.status}


@router.get("/production-signals")
async def list_signals(
    session: SessionDep, _user: CurrentUser,
    product_id: int | None = None, status_filter: str | None = None, limit: int = 50
) -> list[dict]:
    stmt = (
        select(MoProductionSignal)
        .where(MoProductionSignal.deleted_at.is_(None))
        .order_by(MoProductionSignal.computed_at.desc())
        .limit(limit)
    )
    if product_id is not None:
        stmt = stmt.where(MoProductionSignal.product_id == product_id)
    if status_filter is not None:
        stmt = stmt.where(MoProductionSignal.status == status_filter)
    rows = list((await session.execute(stmt)).scalars().all())
    return [{"id": r.id, "product_id": r.product_id, "suggested_qty": r.suggested_qty,
             "avg_daily_demand": r.avg_daily_demand, "status": r.status} for r in rows]


# ── Batch Consolidation (KOB-exclusive) ───────────────────────────────


@router.post("/batch-consolidation/propose")
async def propose_batch(
    product_id: int, session: SessionDep, _user: CurrentUser, window_days: int = 3
) -> dict | None:
    batch = await propose_batch_consolidation(session, product_id, window_days=window_days)
    if batch is None:
        return None
    return {"id": batch.id, "total_mos": batch.total_mos, "total_qty": batch.total_qty,
            "setup_saving_minutes": batch.setup_saving_minutes, "status": batch.status}


@router.get("/batch-consolidation/proposals")
async def list_batch_proposals(
    session: SessionDep, _user: CurrentUser, status_filter: str | None = None
) -> list[dict]:
    stmt = (
        select(BatchConsolidation)
        .where(BatchConsolidation.deleted_at.is_(None))
        .options(selectinload(BatchConsolidation.items))
        .order_by(BatchConsolidation.proposed_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(BatchConsolidation.status == status_filter)
    rows = list((await session.execute(stmt)).scalars().all())
    return [{"id": r.id, "product_id": r.product_id, "total_mos": r.total_mos,
             "total_qty": r.total_qty, "setup_saving_minutes": r.setup_saving_minutes,
             "status": r.status} for r in rows]


@router.post("/batch-consolidation/proposals/{batch_id}/accept")
async def accept_batch(batch_id: int, session: SessionDep, _user: CurrentUser) -> dict:
    batch = await session.get(BatchConsolidation, batch_id, options=[selectinload(BatchConsolidation.items)])
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "batch proposal not found")
    if batch.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "batch is not pending")
    batch.status = "accepted"
    batch.reviewed_at = datetime.now(UTC)
    batch.reviewed_by_id = _user.id
    await session.flush()
    return {"id": batch.id, "status": batch.status}

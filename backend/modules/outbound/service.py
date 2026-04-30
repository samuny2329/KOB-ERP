"""Outbound business logic — order state transitions + dispatch helpers."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models_audit import append_activity
from backend.core.workflow import WorkflowError
from backend.modules.outbound.models import DispatchBatch, Order, OrderLine, ScanItem


# Order state guards --------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp_state_timestamp(order: Order, target: str) -> None:
    """Set the milestone timestamp matching the new state."""
    when = _now()
    if target == "picking":
        order.pick_start_at = when
    elif target == "picked":
        order.picked_at = when
    elif target == "packing":
        order.pack_start_at = when
    elif target == "packed":
        order.packed_at = when
    elif target == "shipped":
        order.shipped_at = when


async def transition_order(
    session: AsyncSession,
    order: Order,
    target: str,
    actor_id: int | None = None,
) -> Order:
    """Move ``order`` to ``target`` and append an entry to the activity log."""
    try:
        order.transition(target)
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    _stamp_state_timestamp(order, target)
    await append_activity(
        session,
        actor_id=actor_id,
        action=f"order.{target}",
        ref=order.ref,
        code=order.id and str(order.id) or None,
        note=f"order {order.ref} → {target}",
    )
    return order


async def create_order_with_lines(
    session: AsyncSession,
    *,
    ref: str,
    customer_name: str,
    platform: str,
    courier_id: int | None,
    note: str | None,
    lines_data: list[dict],
    actor_id: int | None = None,
) -> Order:
    order = Order(
        ref=ref,
        customer_name=customer_name,
        platform=platform,
        courier_id=courier_id,
        note=note,
        state="pending",
        sla_start_at=_now(),
    )
    session.add(order)
    await session.flush()

    for line_data in lines_data:
        session.add(OrderLine(order_id=order.id, **line_data))
    await session.flush()
    await session.refresh(order, attribute_names=["lines"])

    await append_activity(
        session,
        actor_id=actor_id,
        action="order.created",
        ref=order.ref,
        code=str(order.id),
        note=f"order {order.ref} for {customer_name} ({len(lines_data)} lines)",
    )
    return order


# Dispatch batch helpers ----------------------------------------------


async def _next_batch_name(session: AsyncSession) -> str:
    n = len((await session.execute(select(DispatchBatch))).scalars().all()) + 1
    return f"DISP/{n:06d}"


async def create_dispatch_batch(
    session: AsyncSession,
    *,
    courier_id: int,
    work_date: datetime | None,
    note: str | None,
    actor_id: int | None = None,
) -> DispatchBatch:
    name = await _next_batch_name(session)
    batch = DispatchBatch(
        name=name,
        courier_id=courier_id,
        work_date=work_date,
        note=note,
        state="draft",
    )
    session.add(batch)
    await session.flush()
    await append_activity(
        session,
        actor_id=actor_id,
        action="dispatch.created",
        ref=batch.name,
        code=str(batch.id),
    )
    return batch


async def add_scan(
    session: AsyncSession,
    *,
    batch: DispatchBatch,
    barcode: str,
    order_id: int | None,
    actor_id: int | None,
) -> ScanItem:
    if batch.state not in {"draft", "scanning"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"can't scan into a {batch.state!r} batch",
        )
    if batch.state == "draft":
        batch.transition("scanning")

    scan = ScanItem(
        batch_id=batch.id,
        order_id=order_id,
        barcode=barcode,
        scanned_at=_now(),
        scanned_by=actor_id,
    )
    session.add(scan)
    await session.flush()
    await append_activity(
        session,
        actor_id=actor_id,
        action="dispatch.scan",
        ref=batch.name,
        code=barcode,
        note=f"scan {barcode} into {batch.name}",
    )
    return scan


async def transition_batch(
    session: AsyncSession,
    batch: DispatchBatch,
    target: str,
    actor_id: int | None = None,
) -> DispatchBatch:
    try:
        batch.transition(target)
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if target == "dispatched":
        batch.dispatched_at = _now()
        batch.dispatched_by = actor_id
    await append_activity(
        session,
        actor_id=actor_id,
        action=f"dispatch.{target}",
        ref=batch.name,
        code=str(batch.id),
    )
    return batch

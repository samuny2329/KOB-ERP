"""Inventory business logic — transfer state transitions + quant updates."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.workflow import WorkflowError
from backend.modules.inventory.models import StockQuant, Transfer, TransferLine, TransferType


async def _next_transfer_name(session: AsyncSession, transfer_type: TransferType) -> str:
    """Return ``"<prefix>/000123"`` — the next sequence number for this type.

    Uses ``COUNT(*)`` rather than a real sequence — fine for the volume KOB
    expects (hundreds/day).  Replace with a Postgres SEQUENCE per type once
    contention becomes an issue.
    """
    count = (
        await session.execute(
            select(Transfer)
            .where(Transfer.transfer_type_id == transfer_type.id)
        )
    ).scalars().all()
    n = len(count) + 1
    return f"{transfer_type.sequence_prefix}/{n:06d}"


async def _quant_for(
    session: AsyncSession, location_id: int, product_id: int, lot_id: int | None
) -> StockQuant:
    """Get-or-create the StockQuant row for this (location, product, lot)."""
    stmt = select(StockQuant).where(
        StockQuant.location_id == location_id,
        StockQuant.product_id == product_id,
        StockQuant.lot_id.is_(lot_id) if lot_id is None else StockQuant.lot_id == lot_id,
    )
    quant = (await session.execute(stmt)).scalar_one_or_none()
    if quant is None:
        quant = StockQuant(
            location_id=location_id,
            product_id=product_id,
            lot_id=lot_id,
            quantity=0,
            reserved_quantity=0,
        )
        session.add(quant)
        await session.flush()
    return quant


async def confirm_transfer(session: AsyncSession, transfer: Transfer) -> Transfer:
    """draft → confirmed.  Validates lines exist and quantities are positive."""
    if not transfer.lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "transfer has no lines")
    for line in transfer.lines:
        if float(line.quantity_demand) <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"line {line.id}: quantity_demand must be > 0",
            )
    try:
        transfer.transition("confirmed")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return transfer


async def complete_transfer(session: AsyncSession, transfer: Transfer) -> Transfer:
    """confirmed → done.  Moves stock from source to destination per line.

    For Phase 2a we use ``quantity_done`` if set, else ``quantity_demand``.
    No reservation logic yet — destination is credited unconditionally.
    """
    if transfer.state != "confirmed":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"only 'confirmed' transfers can be completed (current: {transfer.state})",
        )

    for line in transfer.lines:
        qty = float(line.quantity_done) if float(line.quantity_done) > 0 else float(line.quantity_demand)
        line.quantity_done = qty

        src_id = line.source_location_id or transfer.source_location_id
        dst_id = line.dest_location_id or transfer.dest_location_id

        src = await _quant_for(session, src_id, line.product_id, line.lot_id)
        dst = await _quant_for(session, dst_id, line.product_id, line.lot_id)
        src.quantity = float(src.quantity) - qty
        dst.quantity = float(dst.quantity) + qty

    try:
        transfer.transition("done")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    transfer.done_date = datetime.now(UTC)
    return transfer


async def cancel_transfer(session: AsyncSession, transfer: Transfer) -> Transfer:
    try:
        transfer.transition("cancelled")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return transfer


async def create_transfer_with_lines(
    session: AsyncSession,
    *,
    transfer_type: TransferType,
    source_location_id: int,
    dest_location_id: int,
    origin: str | None,
    scheduled_date: datetime | None,
    note: str | None,
    lines_data: list[dict],
) -> Transfer:
    name = await _next_transfer_name(session, transfer_type)
    transfer = Transfer(
        name=name,
        transfer_type_id=transfer_type.id,
        source_location_id=source_location_id,
        dest_location_id=dest_location_id,
        origin=origin,
        scheduled_date=scheduled_date,
        note=note,
        state="draft",
    )
    session.add(transfer)
    await session.flush()

    for line_data in lines_data:
        line = TransferLine(transfer_id=transfer.id, **line_data)
        session.add(line)

    await session.flush()
    await session.refresh(transfer, attribute_names=["lines"])
    return transfer

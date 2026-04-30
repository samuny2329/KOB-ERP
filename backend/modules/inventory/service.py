"""Inventory business logic — transfer state transitions + quant updates."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.workflow import WorkflowError
from backend.modules.inventory.models import StockQuant, Transfer, TransferLine, TransferType
from backend.modules.inventory.models_advanced import (
    LandedCost,
    LandedCostLine,
    LandedCostTransfer,
    PutawayRule,
    ScrapOrder,
    StockValuationLayer,
)


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


# ── Putaway Rules ──────────────────────────────────────────────────────


async def apply_putaway_rule(
    session: AsyncSession,
    location_id: int,
    product_id: int | None,
    category_id: int | None,
) -> int:
    """Return the best destination sub-location for incoming goods.

    Priority: product-specific rule > category rule > original location.
    Rules are evaluated in ascending ``sequence`` order.
    """
    stmt = (
        select(PutawayRule)
        .where(
            PutawayRule.location_id == location_id,
            PutawayRule.active.is_(True),
        )
        .order_by(PutawayRule.sequence)
    )
    rules = list((await session.execute(stmt)).scalars().all())

    # Product-specific match first
    if product_id is not None:
        for rule in rules:
            if rule.product_id == product_id:
                return rule.location_dest_id

    # Category match second
    if category_id is not None:
        for rule in rules:
            if rule.product_category_id == category_id and rule.product_id is None:
                return rule.location_dest_id

    return location_id


# ── Returns ────────────────────────────────────────────────────────────


async def create_return_transfer(
    session: AsyncSession,
    original: Transfer,
    lines_data: list[dict],
) -> Transfer:
    """Create a reverse transfer (return) from a completed transfer.

    ``lines_data`` is a list of ``{"transfer_line_id": int, "quantity": float}``.
    The return swaps source / destination and sets ``is_return=True``.
    """
    if original.state != "done":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "can only return a completed (done) transfer",
        )

    line_map = {line.id: line for line in original.lines}
    return_transfer = Transfer(
        name=f"RETURN/{original.name}",
        transfer_type_id=original.transfer_type_id,
        source_location_id=original.dest_location_id,
        dest_location_id=original.source_location_id,
        origin=original.name,
        is_return=True,
        origin_transfer_id=original.id,
        state="draft",
    )
    session.add(return_transfer)
    await session.flush()

    for item in lines_data:
        src_line = line_map.get(item["transfer_line_id"])
        if src_line is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"transfer_line_id {item['transfer_line_id']} not found on original transfer",
            )
        return_line = TransferLine(
            transfer_id=return_transfer.id,
            product_id=src_line.product_id,
            uom_id=src_line.uom_id,
            lot_id=src_line.lot_id,
            quantity_demand=item["quantity"],
            source_location_id=src_line.dest_location_id or original.dest_location_id,
            dest_location_id=src_line.source_location_id or original.source_location_id,
        )
        session.add(return_line)

    await session.flush()
    await session.refresh(return_transfer, attribute_names=["lines"])
    return return_transfer


# ── Backorders ─────────────────────────────────────────────────────────


async def create_backorder(session: AsyncSession, original: Transfer) -> Transfer | None:
    """Create a backorder for under-received / under-shipped lines.

    Returns the new backorder Transfer if any remaining qty exists, else None.
    """
    remaining = [
        line
        for line in original.lines
        if float(line.quantity_demand) - float(line.quantity_done) > 0
    ]
    if not remaining:
        return None

    backorder = Transfer(
        name=f"BO/{original.name}",
        transfer_type_id=original.transfer_type_id,
        source_location_id=original.source_location_id,
        dest_location_id=original.dest_location_id,
        origin=original.name,
        backorder_id=original.id,
        state="draft",
    )
    session.add(backorder)
    await session.flush()

    for line in remaining:
        bo_line = TransferLine(
            transfer_id=backorder.id,
            product_id=line.product_id,
            uom_id=line.uom_id,
            lot_id=line.lot_id,
            quantity_demand=float(line.quantity_demand) - float(line.quantity_done),
            source_location_id=line.source_location_id,
            dest_location_id=line.dest_location_id,
        )
        session.add(bo_line)

    await session.flush()
    await session.refresh(backorder, attribute_names=["lines"])
    return backorder


# ── Scrap ──────────────────────────────────────────────────────────────


async def validate_scrap(session: AsyncSession, scrap: ScrapOrder) -> ScrapOrder:
    """draft → done.  Deducts from source quant, credits scrap location."""
    if scrap.state != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"scrap order must be in draft state (current: {scrap.state})",
        )

    qty = float(scrap.scrap_qty)
    src = await _quant_for(session, scrap.source_location_id, scrap.product_id, scrap.lot_id)
    dst = await _quant_for(session, scrap.scrap_location_id, scrap.product_id, scrap.lot_id)
    src.quantity = float(src.quantity) - qty
    dst.quantity = float(dst.quantity) + qty

    scrap.total_cost = float(scrap.unit_cost) * qty
    scrap.done_at = datetime.now(UTC)

    try:
        scrap.transition("done")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    return scrap


# ── Landed Costs ───────────────────────────────────────────────────────


async def post_landed_cost(session: AsyncSession, lc: LandedCost) -> LandedCost:
    """draft → posted.  Allocates cost across linked transfer lines.

    For each LandedCostLine, cost is spread to transfer lines using
    the line's ``split_method``:
      - equal: divide evenly across all lines
      - by_quantity: weight by quantity_done
      - by_weight / by_volume / by_current_cost: not yet computed
        (falls back to equal split for now)
    Creates a StockValuationLayer per transfer line per cost component.
    """
    if lc.state != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"landed cost must be in draft state (current: {lc.state})",
        )

    # Gather all transfer lines from linked transfers
    transfer_ids = [lt.transfer_id for lt in lc.transfer_links]
    if not transfer_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no transfers linked to landed cost")

    all_lines: list[TransferLine] = []
    for t_id in transfer_ids:
        transfer = await session.get(
            Transfer, t_id, options=[selectinload(Transfer.lines)]
        )
        if transfer is None:
            continue
        all_lines.extend(transfer.lines)

    if not all_lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "linked transfers have no lines")

    for cost_line in lc.lines:
        total_qty = sum(float(l.quantity_done) for l in all_lines) or 1.0
        amount = float(cost_line.amount)

        for tl in all_lines:
            if cost_line.split_method == "by_quantity":
                share = (float(tl.quantity_done) / total_qty) * amount
            else:
                # equal split for all other methods
                share = amount / len(all_lines)

            if share == 0:
                continue

            layer = StockValuationLayer(
                product_id=tl.product_id,
                transfer_id=tl.transfer_id,
                transfer_line_id=tl.id,
                quantity=float(tl.quantity_done),
                unit_cost=share / max(float(tl.quantity_done), 1),
                value=share,
                remaining_qty=float(tl.quantity_done),
                remaining_value=share,
                description=f"Landed cost: {lc.name} / {cost_line.name}",
                landed_cost_id=lc.id,
            )
            session.add(layer)

    lc.posted_at = datetime.now(UTC)
    try:
        lc.transition("posted")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await session.flush()
    return lc

"""Manufacturing business logic — MO workflow, cost tracking, signals, batch consolidation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.workflow import WorkflowError
from backend.modules.mfg.models import (
    BomLine,
    BomTemplate,
    ManufacturingOrder,
    SubconRecon,
    SubconReconLine,
    SubconVendor,
    WorkOrder,
)
from backend.modules.mfg.models_advanced import (
    BatchConsolidation,
    BatchConsolidationItem,
    MoComponentLine,
    MoProductionSignal,
    MoScrap,
    RoutingOperation,
    UnbuildOrder,
    WorkCenterOee,
)


# ── MO State Transitions ───────────────────────────────────────────────


async def confirm_mo(session: AsyncSession, mo: ManufacturingOrder) -> ManufacturingOrder:
    """draft → confirmed.  Auto-generates component lines from BOM."""
    try:
        mo.transition("confirmed")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    # Auto-generate component consumption lines from BOM
    bom = await session.get(BomTemplate, mo.bom_id, options=[selectinload(BomTemplate.lines)])
    if bom:
        ratio = float(mo.qty_planned) / max(float(bom.output_qty), 1)
        for bom_line in bom.lines:
            if bom_line.line_type == "byproduct":
                continue  # by-products are added to finished goods, not consumed
            session.add(
                MoComponentLine(
                    mo_id=mo.id,
                    product_id=bom_line.component_id,
                    uom_id=bom_line.uom_id,
                    qty_demand=float(bom_line.qty) * ratio,
                )
            )
    await session.flush()
    return mo


async def start_mo(session: AsyncSession, mo: ManufacturingOrder) -> ManufacturingOrder:
    """confirmed → in_progress."""
    try:
        mo.transition("in_progress")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    mo.started_at = datetime.now(UTC)
    await session.flush()
    return mo


async def close_mo(session: AsyncSession, mo: ManufacturingOrder) -> ManufacturingOrder:
    """in_progress → to_close.  Computes total cost."""
    try:
        mo.transition("to_close")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await _recompute_mo_cost(session, mo)
    await session.flush()
    return mo


async def complete_mo(session: AsyncSession, mo: ManufacturingOrder) -> ManufacturingOrder:
    """to_close → done."""
    try:
        mo.transition("done")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    mo.completed_at = datetime.now(UTC)
    await session.flush()
    return mo


# ── Cost Computation ───────────────────────────────────────────────────


async def _recompute_mo_cost(session: AsyncSession, mo: ManufacturingOrder) -> None:
    """Accumulate material + labor cost from component lines + work orders."""
    # Material cost
    comp_result = await session.execute(
        select(MoComponentLine).where(MoComponentLine.mo_id == mo.id)
    )
    components = list(comp_result.scalars().all())
    material = sum(float(c.total_cost) for c in components)

    # Labor cost from work orders (duration × work_center cost_per_hour)
    from backend.modules.mfg.models_advanced import WorkCenter
    wo_result = await session.execute(
        select(WorkOrder)
        .where(WorkOrder.mo_id == mo.id, WorkOrder.deleted_at.is_(None))
    )
    work_orders = list(wo_result.scalars().all())

    labor = 0.0
    for wo in work_orders:
        if wo.work_center_id and wo.duration_minutes:
            wc = await session.get(WorkCenter, wo.work_center_id)
            if wc:
                labor += (float(wo.duration_minutes) / 60) * float(wc.cost_per_hour)

    overhead = (material + labor) * 0.05  # 5% overhead — configurable in future

    mo.material_cost = round(material, 2)
    mo.labor_cost = round(labor, 2)
    mo.overhead_cost = round(overhead, 2)
    mo.total_cost = round(material + labor + overhead, 2)


# ── Scrap During Production ────────────────────────────────────────────


async def record_scrap(
    session: AsyncSession,
    mo: ManufacturingOrder,
    product_id: int,
    qty: float,
    reason: str | None,
    lot_id: int | None = None,
    unit_cost: float = 0.0,
) -> MoScrap:
    """Record a scrap event on an in-progress MO."""
    if mo.state not in ("in_progress", "to_close"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"can only scrap on in_progress/to_close MO (current: {mo.state!r})",
        )
    scrap = MoScrap(
        mo_id=mo.id,
        product_id=product_id,
        lot_id=lot_id,
        qty=qty,
        scrap_reason=reason,
        unit_cost=unit_cost,
        total_cost=round(qty * unit_cost, 2),
        scrapped_at=datetime.now(UTC),
    )
    session.add(scrap)
    mo.qty_scrap = float(mo.qty_scrap) + qty
    await session.flush()
    return scrap


# ── Unbuild Orders ─────────────────────────────────────────────────────


async def validate_unbuild(session: AsyncSession, unbuild: UnbuildOrder) -> UnbuildOrder:
    """draft → done.  Returns components to stock by reversing BOM consumption."""
    if unbuild.state != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "unbuild order must be in draft")
    try:
        unbuild.transition("done")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    unbuild.done_at = datetime.now(UTC)
    # Actual WMS stock moves would be created here when WMS integration is complete
    await session.flush()
    return unbuild


# ── Subcon Vendor Quality Score ────────────────────────────────────────


async def recompute_subcon_quality(
    session: AsyncSession, subcon_vendor_id: int
) -> SubconVendor:
    """Recompute variance_rate and quality_score for a subcon vendor.

    Called after every SubconRecon is marked done.
    variance_rate = avg(|qty_variance| / qty_sent) across done recons.
    quality_score = max(0, 100 - variance_rate * 100).
    """
    recons_result = await session.execute(
        select(SubconRecon)
        .where(
            SubconRecon.subcon_vendor_id == subcon_vendor_id,
            SubconRecon.state == "done",
            SubconRecon.deleted_at.is_(None),
        )
        .options(selectinload(SubconRecon.lines))
    )
    recons = list(recons_result.scalars().all())

    rates = []
    for recon in recons:
        for line in recon.lines:
            if float(line.qty_sent) > 0:
                rate = abs(float(line.qty_variance)) / float(line.qty_sent)
                rates.append(rate)

    avg_variance = (sum(rates) / len(rates)) if rates else 0.0
    quality = max(0.0, 100.0 - avg_variance * 100)

    vendor = await session.get(SubconVendor, subcon_vendor_id)
    if vendor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "subcon vendor not found")
    vendor.variance_rate = round(avg_variance, 4)
    vendor.quality_score = round(quality, 2)
    await session.flush()
    return vendor


# ── OEE Computation ────────────────────────────────────────────────────


def compute_oee(
    planned_time: int,
    available_time: int,
    run_time: int,
    ideal_cycle_time: float,
    total_units: int,
    good_units: int,
) -> dict[str, float]:
    """Compute OEE components. Returns availability, performance, quality, oee (0-100)."""
    availability = (available_time / planned_time * 100) if planned_time > 0 else 0.0
    # Performance: run_time-based, ideal vs actual throughput
    ideal_total_time = ideal_cycle_time * total_units
    performance = (ideal_total_time / run_time * 100) if run_time > 0 else 0.0
    performance = min(performance, 100.0)
    quality = (good_units / total_units * 100) if total_units > 0 else 0.0
    oee = availability * performance * quality / 10_000
    return {
        "availability": round(availability, 2),
        "performance": round(performance, 2),
        "quality": round(quality, 2),
        "oee": round(oee, 2),
    }


# ── Demand-driven MO Signal (KOB-exclusive) ───────────────────────────


async def compute_production_signal(
    session: AsyncSession,
    product_id: int,
    current_stock: float,
    wip_qty: float,
    *,
    lookback_days: int = 30,
) -> MoProductionSignal:
    """Compute production suggestion from platform order velocity.

    suggested_qty = (avg_daily × lead_time) + safety - current_stock - wip_qty
    """
    from sqlalchemy import text

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    result = await session.execute(
        text(
            """
            SELECT COALESCE(SUM(pol.quantity), 0)
            FROM ops.platform_order po
            JOIN ops.platform_order_line pol ON pol.platform_order_id = po.id
            WHERE pol.product_id = :product_id
              AND po.created_at >= :cutoff
              AND po.status NOT IN ('cancelled', 'returned')
              AND po.deleted_at IS NULL
            """
        ),
        {"product_id": product_id, "cutoff": cutoff},
    )
    row = result.fetchone()
    total_sold = float(row[0]) if row else 0.0
    avg_daily = total_sold / lookback_days

    # Best BOM for this product
    bom = (
        await session.execute(
            select(BomTemplate).where(
                BomTemplate.product_id == product_id,
                BomTemplate.active.is_(True),
            ).limit(1)
        )
    ).scalar_one_or_none()

    lead_time = 3  # default mfg lead time
    safety = avg_daily * 1.5
    suggested = max(0.0, (avg_daily * lead_time) + safety - current_stock - wip_qty)

    signal = MoProductionSignal(
        product_id=product_id,
        bom_id=bom.id if bom else None,
        platform="all",
        avg_daily_demand=round(avg_daily, 4),
        lead_time_days=lead_time,
        current_stock=current_stock,
        wip_qty=wip_qty,
        suggested_qty=round(suggested, 4),
        computed_at=datetime.now(UTC),
        status="open",
    )
    session.add(signal)
    await session.flush()
    return signal


# ── Batch Consolidation Engine (KOB-exclusive) ───────────────────────


async def propose_batch_consolidation(
    session: AsyncSession,
    product_id: int,
    *,
    window_days: int = 3,
    setup_minutes_per_run: int = 30,
) -> BatchConsolidation | None:
    """Scan draft MOs for the same product and propose a consolidated run.

    Returns None if fewer than 2 MOs found.
    Saving = setup_minutes_per_run × (n_mos - 1).
    """
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=window_days)
    stmt = (
        select(ManufacturingOrder)
        .where(
            ManufacturingOrder.product_id == product_id,
            ManufacturingOrder.state == "draft",
            ManufacturingOrder.deleted_at.is_(None),
        )
    )
    mos = list((await session.execute(stmt)).scalars().all())

    if len(mos) < 2:
        return None

    total_qty = sum(float(m.qty_planned) for m in mos)
    saving = setup_minutes_per_run * (len(mos) - 1)

    batch = BatchConsolidation(
        product_id=product_id,
        status="pending",
        total_mos=len(mos),
        total_qty=total_qty,
        setup_saving_minutes=saving,
        window_days=window_days,
        proposed_at=datetime.now(UTC),
    )
    session.add(batch)
    await session.flush()

    for mo in mos:
        session.add(BatchConsolidationItem(batch_id=batch.id, mo_id=mo.id))

    await session.flush()
    await session.refresh(batch, ["items"])
    return batch

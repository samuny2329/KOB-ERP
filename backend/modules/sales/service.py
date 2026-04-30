"""Sales business logic — promise-to-deliver, credit check, LTV scoring,
return validation, intercompany mirror PO creation.

Heuristic / first-cut implementations: enough to demonstrate the contract
and feed the API.  Productionising (fancier ML for P2D, Celery-driven LTV
refresh, transfer pricing engine) lives in later phases.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.workflow import WorkflowError
from backend.modules.inventory.models import StockQuant
from backend.modules.ops.models import KpiAlert
from backend.modules.sales.models import Customer, SalesOrder, SoLine
from backend.modules.sales.models_advanced import (
    CustomerLtvSnapshot,
    IntercompanyTransfer,
    ReturnOrder,
    ReturnLine,
)


# ── Promise to deliver ─────────────────────────────────────────────────


async def promise_to_deliver(
    session: AsyncSession,
    customer: Customer,
    line_items: list[dict],
    requested_warehouse_id: int | None = None,
) -> tuple[date, float, int | None]:
    """Compute a promise date + confidence score for a draft SO.

    Heuristic v1 — production-grade lookups (postal-code zone leadtimes,
    warehouse SLA, courier capacity) plug in later without changing the
    signature.

    Returns:
        (promise_date, confidence ∈ [0..1], chosen_warehouse_id)
    """
    today = date.today()

    # Aggregate availability per warehouse for every requested SKU.
    product_ids = [item["product_id"] for item in line_items]
    if not product_ids:
        return (today, 0.0, requested_warehouse_id)

    stmt = (
        select(StockQuant.product_id, func.sum(StockQuant.quantity))
        .where(StockQuant.product_id.in_(product_ids))
        .group_by(StockQuant.product_id)
    )
    on_hand = {pid: float(qty or 0) for pid, qty in (await session.execute(stmt)).all()}

    short_skus = [
        item["product_id"]
        for item in line_items
        if on_hand.get(item["product_id"], 0) < float(item["qty"])
    ]

    # Default lead time: 1d pick + 1d pack + 2d courier; +5d if shortfall.
    base_days = 4
    confidence = 0.85
    if short_skus:
        base_days += 5
        confidence = 0.55
    if customer.blocked:
        confidence = 0.3

    return (today + timedelta(days=base_days), round(confidence, 2), requested_warehouse_id)


# ── Credit check ───────────────────────────────────────────────────────


async def customer_credit_check(
    customer: Customer, draft_amount: float
) -> tuple[bool, str | None, float]:
    """Decide whether a draft SO total is allowed against the customer's credit.

    Returns ``(allowed, reason_if_not, available_credit)``.
    """
    if customer.blocked:
        return False, customer.blocked_reason or "customer is blocked", 0.0

    consumed = float(customer.credit_consumed or 0)
    limit = float(customer.credit_limit or 0)
    available = max(0.0, limit - consumed)

    if limit == 0:  # No limit set → unlimited credit
        return True, None, float("inf")

    if consumed + float(draft_amount) > limit:
        return False, f"would exceed credit limit ({available:.2f} available)", available

    return True, None, available


# ── LTV scoring ────────────────────────────────────────────────────────


async def compute_ltv_score(
    session: AsyncSession,
    customer: Customer,
    snapshot_date: date | None = None,
) -> CustomerLtvSnapshot:
    """Roll up the last 90d of activity for ``customer`` into an LTV score.

    Score formula (v1):
        revenue_90d × repeat_rate × (1 − return_rate)

    The snapshot is appended (history kept) and the customer's
    ``ltv_score`` is updated to the latest score.
    """
    snap_date = snapshot_date or date.today()
    window_start = snap_date - timedelta(days=90)

    # Sum revenue + count distinct order days in window.
    rev_stmt = (
        select(
            func.coalesce(func.sum(SalesOrder.total_amount), 0),
            func.count(SalesOrder.id),
        )
        .where(
            SalesOrder.customer_id == customer.id,
            SalesOrder.state.in_(("confirmed", "picking", "shipped", "invoiced")),
            SalesOrder.order_date >= window_start,
            SalesOrder.order_date <= snap_date,
        )
    )
    rev, order_count = (await session.execute(rev_stmt)).one()
    revenue_90d = float(rev or 0)
    order_count_90d = int(order_count or 0)
    aov = revenue_90d / order_count_90d if order_count_90d > 0 else 0.0

    # Returns as a fraction of revenue.
    ret_stmt = (
        select(func.coalesce(func.sum(ReturnOrder.refund_amount), 0))
        .where(
            ReturnOrder.sales_order_id == SalesOrder.id,
            SalesOrder.customer_id == customer.id,
            ReturnOrder.state.in_(("restocked", "scrapped")),
            ReturnOrder.completed_at >= datetime.combine(window_start, datetime.min.time(), tzinfo=UTC),
        )
    )
    refund_total = float((await session.execute(ret_stmt)).scalar() or 0)
    return_rate = (refund_total / revenue_90d) if revenue_90d > 0 else 0.0

    # Repeat rate: ≥2 orders → 1.0, exactly 1 → 0.5, 0 → 0.
    repeat_rate = 1.0 if order_count_90d >= 2 else (0.5 if order_count_90d == 1 else 0.0)

    score = revenue_90d * repeat_rate * (1 - return_rate)

    snap = CustomerLtvSnapshot(
        customer_id=customer.id,
        snapshot_date=snap_date,
        revenue_90d=revenue_90d,
        order_count_90d=order_count_90d,
        repeat_rate=repeat_rate,
        return_rate=round(return_rate, 4),
        avg_order_value=aov,
        score=round(score, 2),
        breakdown={
            "revenue_90d": revenue_90d,
            "order_count_90d": order_count_90d,
            "aov": aov,
            "refund_total_90d": refund_total,
        },
    )
    session.add(snap)
    customer.ltv_score = round(score, 2)
    await session.flush()
    return snap


# ── Return validation ──────────────────────────────────────────────────


async def validate_return(
    session: AsyncSession,
    return_order: ReturnOrder,
    target: str,
) -> ReturnOrder:
    """Move a ReturnOrder forward, with side-effects matching the new state.

    target ∈ {received, restocked, scrapped, cancelled}.  On ``restocked``
    we add stock back to ``receipt_location_id``; on ``scrapped`` we don't
    touch stock (assumed already at scrap location).
    """
    try:
        return_order.transition(target)
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    now = datetime.now(UTC)
    if target == "received":
        return_order.received_at = now

    elif target == "restocked":
        if return_order.receipt_location_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "restocked requires receipt_location_id",
            )
        for line in return_order.lines:
            qty = float(line.qty_returned)
            line.qty_restocked = qty
            quant_stmt = select(StockQuant).where(
                StockQuant.location_id == return_order.receipt_location_id,
                StockQuant.product_id == line.product_id,
                StockQuant.lot_id.is_(line.lot_id) if line.lot_id is None else StockQuant.lot_id == line.lot_id,
            )
            quant = (await session.execute(quant_stmt)).scalar_one_or_none()
            if quant is None:
                quant = StockQuant(
                    location_id=return_order.receipt_location_id,
                    product_id=line.product_id,
                    lot_id=line.lot_id,
                    quantity=0,
                    reserved_quantity=0,
                )
                session.add(quant)
                await session.flush()
            quant.quantity = float(quant.quantity) + qty
        return_order.completed_at = now

    elif target == "scrapped":
        for line in return_order.lines:
            line.qty_scrapped = float(line.qty_returned)
        return_order.completed_at = now

    return return_order


# ── Intercompany mirror PO ─────────────────────────────────────────────


async def create_intercompany_mirror(
    session: AsyncSession,
    sales_order: SalesOrder,
    fulfillment_company_id: int,
    transfer_pricing_method: str = "cost_plus",
    transfer_pricing_pct: float = 0,
) -> IntercompanyTransfer:
    """Create an IntercompanyTransfer when a SO ships from a different company.

    Mirror PO creation is queued — the actual ``purchase.purchase_order``
    row is built by the purchase service so this module stays decoupled
    from purchase internals.  We just emit the bridge row in ``draft``.
    """
    if sales_order.company_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "sales order has no company_id — cannot mirror",
        )
    if sales_order.company_id == fulfillment_company_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "fulfillment company matches SO company — no intercompany flow needed",
        )

    transfer_amount = float(sales_order.total_amount or 0)
    if transfer_pricing_method == "cost_plus":
        transfer_amount = transfer_amount * (1 + transfer_pricing_pct / 100)

    bridge = IntercompanyTransfer(
        sales_order_id=sales_order.id,
        so_company_id=sales_order.company_id,
        fulfillment_company_id=fulfillment_company_id,
        state="draft",
        transfer_amount=Decimal(str(round(transfer_amount, 2))),
        transfer_pricing_method=transfer_pricing_method,
        transfer_pricing_pct=Decimal(str(transfer_pricing_pct)),
    )
    session.add(bridge)
    await session.flush()
    return bridge

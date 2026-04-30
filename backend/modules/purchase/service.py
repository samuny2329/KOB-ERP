"""Purchase business logic — PO workflow, auto-receipt, vendor scoring, demand signals."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from statistics import mean, stdev

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.modules.purchase.models import PoLine, PurchaseOrder, Receipt, ReceiptLine, Vendor
from backend.modules.purchase.models_advanced import (
    DemandSignal,
    PoConsolidationItem,
    PoConsolidationProposal,
    ProcurementBudget,
    SupplierPricelist,
    VendorPerformance,
    WhtCertificate,
)


# ── PO Confirmation + auto-receipt ────────────────────────────────────


async def confirm_purchase_order(
    session: AsyncSession,
    po: PurchaseOrder,
    *,
    auto_create_receipt: bool = True,
) -> PurchaseOrder:
    """Confirm a PO (draft/sent → confirmed) and optionally auto-create a receipt draft.

    If the vendor has a lead_time_days set and expected_date is not manually
    provided, it is computed as order_date + lead_time_days.
    """
    if po.state not in ("draft", "sent", "waiting_approval"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot confirm PO in state {po.state!r}",
        )
    if po.approval_state == "pending":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "PO is waiting for approval — cannot confirm directly",
        )

    vendor = await session.get(Vendor, po.vendor_id)
    if vendor and not po.expected_date:
        po.expected_date = po.order_date + timedelta(days=vendor.lead_time_days)

    po.state = "confirmed"
    po.confirmed_at = datetime.now(UTC)
    await session.flush()

    if auto_create_receipt:
        await _auto_create_receipt(session, po)

    return po


async def _auto_create_receipt(session: AsyncSession, po: PurchaseOrder) -> Receipt:
    """Create a draft receipt for a confirmed PO."""
    await session.refresh(po, ["lines"])
    count = len(
        list(
            (
                await session.execute(
                    select(Receipt).where(Receipt.purchase_order_id == po.id)
                )
            ).scalars().all()
        )
    )
    number = f"GR/{po.number}/{count + 1:03d}"
    receipt = Receipt(
        number=number,
        purchase_order_id=po.id,
        state="draft",
        received_date=date.today(),
    )
    session.add(receipt)
    await session.flush()

    for line in po.lines:
        receipt_line = ReceiptLine(
            receipt_id=receipt.id,
            po_line_id=line.id,
            product_id=line.product_id,
            qty_received=float(line.qty_ordered),
            qty_accepted=0,
            qty_rejected=0,
        )
        session.add(receipt_line)

    await session.flush()
    return receipt


# ── Budget control ─────────────────────────────────────────────────────


async def check_and_apply_budget(
    session: AsyncSession, po: PurchaseOrder
) -> tuple[bool, str]:
    """Check budget availability.

    Returns (ok, message).  If auto_block_overrun is True and the PO
    would exceed the remaining budget, ok=False and the PO should enter
    waiting_approval state instead of confirmed.
    """
    if po.budget_id is None:
        return True, "no budget assigned"

    budget = await session.get(ProcurementBudget, po.budget_id)
    if budget is None or budget.state != "active":
        return True, "budget not active"

    remaining = float(budget.total_budget) - float(budget.committed_amount)
    if float(po.total_amount) > remaining:
        if budget.auto_block_overrun:
            return False, f"PO total {po.total_amount} exceeds remaining budget {remaining:.2f}"
        # Warn but allow
    budget.committed_amount = float(budget.committed_amount) + float(po.total_amount)
    return True, "ok"


# ── Vendor Performance Scoring (KOB-exclusive) ────────────────────────


async def recompute_vendor_performance(
    session: AsyncSession, vendor_id: int, year: int, month: int
) -> VendorPerformance:
    """Recompute KPI score for a vendor for a given month.

    Called after every Receipt validation.
    Scores are clamped 0–100.
    """
    # Pull all POs and receipts for this vendor in the trailing 3 months
    period_start = date(year, month, 1) - timedelta(days=90)

    pos_result = await session.execute(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrder.order_date >= period_start,
            PurchaseOrder.deleted_at.is_(None),
        )
        .options(selectinload(PurchaseOrder.lines))
    )
    pos = list(pos_result.scalars().all())

    receipts_result = await session.execute(
        select(Receipt)
        .where(
            Receipt.purchase_order_id.in_([p.id for p in pos]),
            Receipt.state == "done",
            Receipt.deleted_at.is_(None),
        )
        .options(selectinload(Receipt.lines))
    )
    receipts = list(receipts_result.scalars().all())

    # On-time rate: receipt.validated_at <= po.expected_date
    on_time = 0
    for r in receipts:
        po = next((p for p in pos if p.id == r.purchase_order_id), None)
        if po and po.expected_date and r.validated_at:
            if r.validated_at.date() <= po.expected_date:
                on_time += 1
    on_time_rate = (on_time / len(receipts) * 100) if receipts else 0.0

    # Fill rate: sum qty_accepted / sum qty_ordered
    total_ordered = sum(float(l.qty_ordered) for p in pos for l in p.lines)
    total_accepted = sum(float(l.qty_accepted) for r in receipts for l in r.lines)
    fill_rate = min(total_accepted / total_ordered * 100, 100) if total_ordered else 0.0

    # Quality rate: qty_accepted / qty_received
    total_received = sum(float(l.qty_received) for r in receipts for l in r.lines)
    quality_rate = min(total_accepted / total_received * 100, 100) if total_received else 0.0

    # Price stability: 1 - cv (coefficient of variation)
    prices = [float(l.unit_price) for p in pos for l in p.lines]
    if len(prices) >= 2 and mean(prices) > 0:
        cv = stdev(prices) / mean(prices)
        price_stability = max(0.0, (1 - cv) * 100)
    else:
        price_stability = 100.0

    overall = (on_time_rate * 0.35 + fill_rate * 0.30 + quality_rate * 0.25 + price_stability * 0.10)

    # Upsert performance record
    existing = (
        await session.execute(
            select(VendorPerformance).where(
                VendorPerformance.vendor_id == vendor_id,
                VendorPerformance.period_year == year,
                VendorPerformance.period_month == month,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = VendorPerformance(vendor_id=vendor_id, period_year=year, period_month=month)
        session.add(existing)

    existing.on_time_rate = round(on_time_rate, 2)
    existing.fill_rate = round(fill_rate, 2)
    existing.quality_rate = round(quality_rate, 2)
    existing.price_stability = round(price_stability, 2)
    existing.overall_score = round(overall, 2)
    existing.po_count = len(pos)
    existing.receipt_count = len(receipts)
    existing.computed_at = datetime.now(UTC)

    # Update vendor.performance_score with latest overall
    vendor = await session.get(Vendor, vendor_id)
    if vendor:
        vendor.performance_score = existing.overall_score

    await session.flush()
    return existing


# ── WHT Certificate auto-generate ─────────────────────────────────────


async def generate_wht_certificate(
    session: AsyncSession, po: PurchaseOrder
) -> WhtCertificate:
    """Auto-generate a WHT certificate from vendor defaults."""
    vendor = await session.get(Vendor, po.vendor_id)
    if vendor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vendor not found")

    base = float(po.subtotal)
    rate = float(vendor.wht_rate)
    wht_amount = round(base * rate / 100, 2)
    today = date.today()

    cert = WhtCertificate(
        purchase_order_id=po.id,
        vendor_id=po.vendor_id,
        wht_type=vendor.wht_type,
        wht_rate=rate,
        base_amount=base,
        wht_amount=wht_amount,
        payment_date=today,
        period_month=today.month,
        period_year=today.year,
    )
    session.add(cert)
    await session.flush()
    return cert


# ── Supplier best price lookup ─────────────────────────────────────────


async def get_best_supplier_price(
    session: AsyncSession, vendor_id: int, product_id: int, qty: float
) -> SupplierPricelist | None:
    """Return the best matching pricelist entry for a vendor/product/qty combination.

    Rules: active, effective_from <= today <= effective_to (or None), min_qty <= qty.
    Picks the highest min_qty that still satisfies qty (best volume bracket).
    """
    today = date.today()
    stmt = (
        select(SupplierPricelist)
        .where(
            SupplierPricelist.vendor_id == vendor_id,
            SupplierPricelist.product_id == product_id,
            SupplierPricelist.active.is_(True),
            SupplierPricelist.min_qty <= qty,
            (SupplierPricelist.effective_from.is_(None)) | (SupplierPricelist.effective_from <= today),
            (SupplierPricelist.effective_to.is_(None)) | (SupplierPricelist.effective_to >= today),
        )
        .order_by(SupplierPricelist.min_qty.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# ── Demand Signal computation (KOB-exclusive) ─────────────────────────


async def compute_demand_signals(
    session: AsyncSession,
    product_id: int,
    current_on_hand: float,
    *,
    lookback_days: int = 30,
    safety_stock_multiplier: float = 1.5,
) -> DemandSignal:
    """Compute a purchase suggestion from platform order velocity.

    Reads ops.platform_order data via raw SQL to avoid circular imports.
    ``avg_daily_sales`` = total units sold in last ``lookback_days`` / lookback_days.
    ``suggested_qty`` = (avg_daily_sales × lead_time_days × safety_multiplier) - on_hand.
    """
    from sqlalchemy import func, text

    # Average daily sales from platform orders in lookback window
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    result = await session.execute(
        text(
            """
            SELECT COALESCE(SUM(pol.quantity), 0) as total_qty
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

    # Best vendor for this product
    best_price = (
        await session.execute(
            select(SupplierPricelist)
            .where(
                SupplierPricelist.product_id == product_id,
                SupplierPricelist.active.is_(True),
            )
            .order_by(SupplierPricelist.price)
            .limit(1)
        )
    ).scalar_one_or_none()

    lead_time = best_price.lead_time_days if best_price else 7
    safety = avg_daily * safety_stock_multiplier
    suggested = max(0.0, (avg_daily * lead_time) + safety - current_on_hand)

    signal = DemandSignal(
        product_id=product_id,
        vendor_id=best_price.vendor_id if best_price else None,
        platform="all",
        avg_daily_sales=round(avg_daily, 4),
        lead_time_days=lead_time,
        safety_stock=round(safety, 4),
        current_on_hand=current_on_hand,
        suggested_qty=round(suggested, 4),
        suggested_price=best_price.price if best_price else None,
        computed_at=datetime.now(UTC),
        status="open",
    )
    session.add(signal)
    await session.flush()
    return signal


# ── PO Consolidation Engine (KOB-exclusive) ───────────────────────────


async def propose_consolidation(
    session: AsyncSession, vendor_id: int, *, window_days: int = 7
) -> PoConsolidationProposal | None:
    """Scan draft POs for a vendor within window_days and propose consolidation.

    Returns None if fewer than 2 POs found (nothing to consolidate).
    Estimated saving = 3% of original total (conservative volume discount estimate).
    """
    cutoff = date.today() - timedelta(days=window_days)
    stmt = (
        select(PurchaseOrder)
        .where(
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrder.state == "draft",
            PurchaseOrder.order_date >= cutoff,
            PurchaseOrder.deleted_at.is_(None),
        )
        .options(selectinload(PurchaseOrder.lines))
    )
    draft_pos = list((await session.execute(stmt)).scalars().all())

    if len(draft_pos) < 2:
        return None

    original_total = sum(float(p.total_amount) for p in draft_pos)
    saving = round(original_total * 0.03, 2)
    total_lines = sum(len(p.lines) for p in draft_pos)

    proposal = PoConsolidationProposal(
        vendor_id=vendor_id,
        status="pending",
        total_lines=total_lines,
        original_total=original_total,
        estimated_saving=saving,
        saving_pct=3.0,
        window_days=window_days,
        proposed_at=datetime.now(UTC),
    )
    session.add(proposal)
    await session.flush()

    for po in draft_pos:
        session.add(PoConsolidationItem(proposal_id=proposal.id, purchase_order_id=po.id))

    await session.flush()
    await session.refresh(proposal, ["items"])
    return proposal

"""Sales business logic — confirmation, pricelist, RMA, intercompany, margins."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.workflow import WorkflowError
from backend.modules.sales.models import Customer, SalesOrder, SoLine
from backend.modules.sales.models_advanced import (
    EtaxInvoiceRef,
    IntercompanySalesOrder,
    PlatformFeeRule,
    RmaLine,
    RmaOrder,
    SalesPricelist,
    SalesPriceRule,
    SoMarginLine,
)


# ── SO State Transitions ───────────────────────────────────────────────


async def send_quotation(session: AsyncSession, so: SalesOrder) -> SalesOrder:
    """draft → sent."""
    try:
        so.transition("sent")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    so.sent_at = datetime.now(UTC)
    await session.flush()
    return so


async def confirm_sales_order(session: AsyncSession, so: SalesOrder) -> SalesOrder:
    """draft|sent → confirmed. Credit check + pricelist pricing + margin snapshot."""
    customer = await session.get(Customer, so.customer_id)
    if customer:
        outstanding = await _get_customer_outstanding(session, so.customer_id, exclude_so=so.id)
        if float(customer.credit_limit) > 0 and outstanding + float(so.total_amount) > float(customer.credit_limit):
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                f"credit limit exceeded: outstanding={outstanding:.2f}, limit={customer.credit_limit}",
            )

    if so.pricelist_id:
        await apply_pricelist(session, so, so.pricelist_id)

    try:
        so.transition("confirmed")
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    so.confirmed_at = datetime.now(UTC)
    await session.flush()

    # Snapshot margins
    await _snapshot_margins(session, so)
    await session.flush()
    return so


async def _get_customer_outstanding(
    session: AsyncSession, customer_id: int, *, exclude_so: int | None = None
) -> float:
    stmt = select(SalesOrder).where(
        SalesOrder.customer_id == customer_id,
        SalesOrder.state.in_(["confirmed", "picking", "shipped"]),
        SalesOrder.deleted_at.is_(None),
    )
    if exclude_so:
        stmt = stmt.where(SalesOrder.id != exclude_so)
    result = await session.execute(stmt)
    orders = result.scalars().all()
    return sum(float(o.total_amount) for o in orders)


async def apply_pricelist(
    session: AsyncSession, so: SalesOrder, pricelist_id: int
) -> SalesOrder:
    """Apply best matching pricelist rule to each SO line."""
    pricelist = await session.get(SalesPricelist, pricelist_id, options=[selectinload(SalesPricelist.rules)])
    if not pricelist:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pricelist not found")

    lines_result = await session.execute(
        select(SoLine).where(SoLine.order_id == so.id)
    )
    lines = list(lines_result.scalars().all())

    today = datetime.now(UTC).date()
    for line in lines:
        best = _find_best_rule(pricelist.rules, line.product_id, float(line.qty_ordered), today)
        if best:
            line.unit_price = float(best.price)
            line.subtotal = round(float(line.unit_price) * float(line.qty_ordered) * (1 - float(line.discount_pct) / 100), 2)

    await session.flush()
    so.pricelist_id = pricelist_id
    return so


def _find_best_rule(
    rules: list[SalesPriceRule],
    product_id: int,
    qty: float,
    today,
) -> SalesPriceRule | None:
    candidates = [
        r for r in rules
        if (r.product_id is None or r.product_id == product_id)
        and float(r.min_qty) <= qty
        and (r.date_from is None or r.date_from <= today)
        and (r.date_to is None or r.date_to >= today)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda r: float(r.price))


async def _snapshot_margins(session: AsyncSession, so: SalesOrder) -> None:
    lines_result = await session.execute(
        select(SoLine).where(SoLine.order_id == so.id)
    )
    lines = list(lines_result.scalars().all())

    for line in lines:
        revenue = float(line.subtotal)
        cogs = float(line.margin_amount) if float(line.margin_amount) > 0 else 0.0
        platform_fee = float(line.platform_fee_amount)
        gross_margin = revenue - cogs - platform_fee
        margin_pct = (gross_margin / revenue) if revenue > 0 else 0.0
        session.add(SoMarginLine(
            so_line_id=line.id,
            cogs=round(cogs, 2),
            platform_fee=round(platform_fee, 2),
            gross_margin=round(gross_margin, 2),
            margin_pct=round(margin_pct, 4),
            captured_at=datetime.now(UTC),
        ))


# ── RMA ───────────────────────────────────────────────────────────────


async def create_rma(
    session: AsyncSession,
    so: SalesOrder,
    number: str,
    lines_data: list[dict],
    reason: str | None = None,
) -> RmaOrder:
    """Create a draft RMA from a delivered SO."""
    if so.state not in ("shipped", "invoiced"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"RMA requires shipped/invoiced SO (current: {so.state!r})",
        )
    rma = RmaOrder(so_id=so.id, number=number, reason=reason, state="draft")
    session.add(rma)
    await session.flush()
    for ld in lines_data:
        session.add(RmaLine(
            rma_id=rma.id,
            product_id=ld["product_id"],
            qty_requested=ld["qty_requested"],
            return_reason=ld.get("return_reason"),
        ))
    await session.flush()
    await session.refresh(rma, ["lines"])
    return rma


# ── Intercompany SO ────────────────────────────────────────────────────


async def create_intercompany_so(
    session: AsyncSession,
    so: SalesOrder,
    target_company_id: int,
    from_company_id: int,
) -> IntercompanySalesOrder:
    """Create an IC-SO record linking this SO to a counterpart company."""
    if so.state != "confirmed":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "intercompany SO can only be created from a confirmed SO",
        )
    ic = IntercompanySalesOrder(
        from_company_id=from_company_id,
        to_company_id=target_company_id,
        so_id=so.id,
        status="pending",
    )
    session.add(ic)
    await session.flush()
    return ic


# ── Margin Computation ─────────────────────────────────────────────────


def compute_so_margin(
    revenue: float,
    cogs: float,
    platform: str | None,
    fee_pct: float = 0.0,
) -> dict[str, float]:
    """Pure function — compute margin breakdown for one SO line."""
    platform_fee = round(revenue * fee_pct / 100, 2)
    gross_margin = revenue - cogs - platform_fee
    margin_pct = (gross_margin / revenue * 100) if revenue > 0 else 0.0
    return {
        "revenue": round(revenue, 2),
        "cogs": round(cogs, 2),
        "platform_fee": platform_fee,
        "gross_margin": round(gross_margin, 2),
        "margin_pct": round(margin_pct, 4),
    }


async def get_active_platform_fee(
    session: AsyncSession, platform: str, company_id: int | None
) -> float:
    """Return current fee_pct for a given platform."""
    from datetime import date
    today = date.today()
    stmt = (
        select(PlatformFeeRule)
        .where(
            PlatformFeeRule.platform == platform,
            PlatformFeeRule.effective_from <= today,
            PlatformFeeRule.deleted_at.is_(None),
        )
        .order_by(PlatformFeeRule.effective_from.desc())
        .limit(1)
    )
    if company_id:
        stmt = stmt.where(PlatformFeeRule.company_id == company_id)
    result = await session.execute(stmt)
    rule = result.scalar_one_or_none()
    return float(rule.fee_pct) if rule else 0.0

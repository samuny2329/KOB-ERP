"""Routes for sales advanced — sales teams, pricelists, returns, LTV,
multi-platform, channel margin, intercompany.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.sales.models import Customer, SalesOrder
from backend.modules.sales.models_advanced import (
    ChannelMargin,
    CustomerLtvSnapshot,
    IntercompanyTransfer,
    LostReason,
    MultiPlatformOrder,
    Pricelist,
    PricelistRule,
    ReturnLine,
    ReturnOrder,
    SalesTeam,
)
from backend.modules.sales.schemas_advanced import (
    ChannelMarginRead,
    CreditCheckResult,
    CustomerLtvSnapshotRead,
    IntercompanyTransferCreate,
    IntercompanyTransferRead,
    LostReasonCreate,
    LostReasonRead,
    MultiPlatformOrderCreate,
    MultiPlatformOrderRead,
    PricelistCreate,
    PricelistRead,
    PricelistRuleCreate,
    PricelistRuleRead,
    PromiseToDeliverResult,
    ReturnOrderCreate,
    ReturnOrderRead,
    SalesTeamCreate,
    SalesTeamRead,
)
from backend.modules.sales.service import (
    compute_ltv_score,
    create_intercompany_mirror,
    customer_credit_check,
    promise_to_deliver,
    validate_return,
)


router = APIRouter(prefix="/sales", tags=["sales-advanced"])


# ── Sales teams ────────────────────────────────────────────────────────


@router.post(
    "/sales-teams", response_model=SalesTeamRead, status_code=status.HTTP_201_CREATED
)
async def create_sales_team(
    body: SalesTeamCreate, session: SessionDep, _user: CurrentUser
) -> SalesTeam:
    team = SalesTeam(**body.model_dump(), active=True)
    session.add(team)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "team code already exists") from exc
    return team


@router.get("/sales-teams", response_model=list[SalesTeamRead])
async def list_sales_teams(session: SessionDep, _user: CurrentUser) -> list[SalesTeam]:
    return list(
        (
            await session.execute(
                select(SalesTeam).where(SalesTeam.deleted_at.is_(None)).order_by(SalesTeam.code)
            )
        )
        .scalars()
        .all()
    )


# ── Pricelists ─────────────────────────────────────────────────────────


@router.post(
    "/pricelists", response_model=PricelistRead, status_code=status.HTTP_201_CREATED
)
async def create_pricelist(
    body: PricelistCreate, session: SessionDep, _user: CurrentUser
) -> Pricelist:
    pl = Pricelist(**body.model_dump(), active=True)
    session.add(pl)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "pricelist code already exists") from exc
    return pl


@router.get("/pricelists", response_model=list[PricelistRead])
async def list_pricelists(session: SessionDep, _user: CurrentUser) -> list[Pricelist]:
    return list(
        (
            await session.execute(
                select(Pricelist).where(Pricelist.deleted_at.is_(None)).order_by(Pricelist.code)
            )
        )
        .scalars()
        .all()
    )


@router.post(
    "/pricelists/{pricelist_id}/rules",
    response_model=PricelistRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_pricelist_rule(
    pricelist_id: int,
    body: PricelistRuleCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> PricelistRule:
    if (await session.get(Pricelist, pricelist_id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pricelist not found")
    payload = body.model_dump()
    payload["pricelist_id"] = pricelist_id
    rule = PricelistRule(**payload, active=True)
    session.add(rule)
    await session.flush()
    return rule


@router.get("/pricelists/{pricelist_id}/rules", response_model=list[PricelistRuleRead])
async def list_pricelist_rules(
    pricelist_id: int, session: SessionDep, _user: CurrentUser
) -> list[PricelistRule]:
    return list(
        (
            await session.execute(
                select(PricelistRule)
                .where(PricelistRule.pricelist_id == pricelist_id)
                .order_by(PricelistRule.sequence)
            )
        )
        .scalars()
        .all()
    )


# ── Lost reasons ───────────────────────────────────────────────────────


@router.post(
    "/lost-reasons", response_model=LostReasonRead, status_code=status.HTTP_201_CREATED
)
async def create_lost_reason(
    body: LostReasonCreate, session: SessionDep, _user: CurrentUser
) -> LostReason:
    reason = LostReason(**body.model_dump(), active=True)
    session.add(reason)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "code already exists") from exc
    return reason


@router.get("/lost-reasons", response_model=list[LostReasonRead])
async def list_lost_reasons(session: SessionDep, _user: CurrentUser) -> list[LostReason]:
    return list(
        (
            await session.execute(
                select(LostReason).where(LostReason.deleted_at.is_(None)).order_by(LostReason.sequence)
            )
        )
        .scalars()
        .all()
    )


# ── Return orders / RMA ────────────────────────────────────────────────


@router.post(
    "/return-orders", response_model=ReturnOrderRead, status_code=status.HTTP_201_CREATED
)
async def create_return_order(
    body: ReturnOrderCreate, session: SessionDep, _user: CurrentUser
) -> ReturnOrder:
    so = await session.get(SalesOrder, body.sales_order_id)
    if so is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sales order not found")

    payload = body.model_dump(exclude={"lines"})
    return_order = ReturnOrder(**payload, state="draft")
    session.add(return_order)
    await session.flush()

    for line in body.lines:
        session.add(ReturnLine(return_order_id=return_order.id, **line.model_dump()))
    await session.flush()
    await session.refresh(return_order, attribute_names=["lines"])
    return return_order


@router.get("/return-orders", response_model=list[ReturnOrderRead])
async def list_return_orders(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
    sales_order_id: int | None = None,
) -> list[ReturnOrder]:
    stmt = (
        select(ReturnOrder)
        .where(ReturnOrder.deleted_at.is_(None))
        .options(selectinload(ReturnOrder.lines))
        .order_by(desc(ReturnOrder.id))
    )
    if state is not None:
        stmt = stmt.where(ReturnOrder.state == state)
    if sales_order_id is not None:
        stmt = stmt.where(ReturnOrder.sales_order_id == sales_order_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/return-orders/{return_id}/transition", response_model=ReturnOrderRead)
async def transition_return(
    return_id: int, target: str, session: SessionDep, _user: CurrentUser
) -> ReturnOrder:
    stmt = (
        select(ReturnOrder)
        .where(ReturnOrder.id == return_id)
        .options(selectinload(ReturnOrder.lines))
    )
    ro = (await session.execute(stmt)).scalar_one_or_none()
    if ro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "return order not found")
    return await validate_return(session, ro, target)


# ── Promise to deliver / credit check ──────────────────────────────────


@router.post("/sales-orders/{so_id}/promise", response_model=PromiseToDeliverResult)
async def post_promise(
    so_id: int, session: SessionDep, _user: CurrentUser
) -> PromiseToDeliverResult:
    stmt = (
        select(SalesOrder)
        .where(SalesOrder.id == so_id)
        .options(selectinload(SalesOrder.lines), selectinload(SalesOrder.customer))
    )
    so = (await session.execute(stmt)).scalar_one_or_none()
    if so is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sales order not found")

    line_items = [
        {"product_id": line.product_id, "qty": float(line.qty_ordered)}
        for line in so.lines
    ]
    promise_date, confidence, wh = await promise_to_deliver(
        session, so.customer, line_items, requested_warehouse_id=so.warehouse_id
    )
    so.promise_date = promise_date
    so.p2d_confidence = confidence
    return PromiseToDeliverResult(
        promise_date=promise_date,
        confidence=confidence,
        available_warehouse_id=wh,
        note="heuristic v1: 4 base days + 5d penalty if shortfall + 0.85→0.55→0.3 confidence ladder",
    )


@router.post("/sales-orders/{so_id}/credit-check", response_model=CreditCheckResult)
async def post_credit_check(
    so_id: int, session: SessionDep, _user: CurrentUser
) -> CreditCheckResult:
    so = await session.get(SalesOrder, so_id)
    if so is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sales order not found")
    customer = await session.get(Customer, so.customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer not found")

    allowed, reason, available = await customer_credit_check(
        customer, float(so.total_amount or 0)
    )
    return CreditCheckResult(
        allowed=allowed,
        reason=reason,
        credit_consumed=float(customer.credit_consumed or 0),
        credit_limit=float(customer.credit_limit or 0),
        available=0.0 if available == float("inf") else available,
    )


# ── LTV ────────────────────────────────────────────────────────────────


@router.post(
    "/customers/{customer_id}/ltv-refresh",
    response_model=CustomerLtvSnapshotRead,
)
async def refresh_ltv(
    customer_id: int, session: SessionDep, _user: CurrentUser
) -> CustomerLtvSnapshot:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer not found")
    return await compute_ltv_score(session, customer)


@router.get(
    "/customers/{customer_id}/ltv-snapshots",
    response_model=list[CustomerLtvSnapshotRead],
)
async def list_ltv_snapshots(
    customer_id: int, session: SessionDep, _user: CurrentUser, limit: int = 30
) -> list[CustomerLtvSnapshot]:
    stmt = (
        select(CustomerLtvSnapshot)
        .where(CustomerLtvSnapshot.customer_id == customer_id)
        .order_by(desc(CustomerLtvSnapshot.snapshot_date))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


# ── Multi-platform link ────────────────────────────────────────────────


@router.post(
    "/sales-orders/{so_id}/multi-platform",
    response_model=MultiPlatformOrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def link_multi_platform(
    so_id: int,
    body: MultiPlatformOrderCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> MultiPlatformOrder:
    if body.sales_order_id != so_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "path/body sales_order_id mismatch")
    bridge = MultiPlatformOrder(**body.model_dump())
    session.add(bridge)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "this SO is already linked to that platform order"
        ) from exc
    return bridge


@router.get(
    "/sales-orders/{so_id}/multi-platform",
    response_model=list[MultiPlatformOrderRead],
)
async def list_multi_platform(
    so_id: int, session: SessionDep, _user: CurrentUser
) -> list[MultiPlatformOrder]:
    stmt = select(MultiPlatformOrder).where(MultiPlatformOrder.sales_order_id == so_id)
    return list((await session.execute(stmt)).scalars().all())


# ── Channel margin ─────────────────────────────────────────────────────


@router.get("/channel-margin", response_model=list[ChannelMarginRead])
async def list_channel_margin(
    session: SessionDep,
    _user: CurrentUser,
    period_start: date | None = None,
    period_end: date | None = None,
    company_id: int | None = None,
) -> list[ChannelMargin]:
    stmt = select(ChannelMargin).order_by(desc(ChannelMargin.period_start))
    if period_start is not None:
        stmt = stmt.where(ChannelMargin.period_start >= period_start)
    if period_end is not None:
        stmt = stmt.where(ChannelMargin.period_end <= period_end)
    if company_id is not None:
        stmt = stmt.where(ChannelMargin.company_id == company_id)
    return list((await session.execute(stmt)).scalars().all())


# ── Intercompany ───────────────────────────────────────────────────────


@router.post(
    "/sales-orders/{so_id}/intercompany",
    response_model=IntercompanyTransferRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_intercompany(
    so_id: int,
    body: IntercompanyTransferCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> IntercompanyTransfer:
    if body.sales_order_id != so_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "path/body sales_order_id mismatch")
    so = await session.get(SalesOrder, so_id)
    if so is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sales order not found")
    return await create_intercompany_mirror(
        session,
        so,
        fulfillment_company_id=body.fulfillment_company_id,
        transfer_pricing_method=body.transfer_pricing_method,
        transfer_pricing_pct=body.transfer_pricing_pct,
    )


@router.get(
    "/sales-orders/{so_id}/intercompany",
    response_model=list[IntercompanyTransferRead],
)
async def list_intercompany(
    so_id: int, session: SessionDep, _user: CurrentUser
) -> list[IntercompanyTransfer]:
    stmt = (
        select(IntercompanyTransfer)
        .where(IntercompanyTransfer.sales_order_id == so_id)
        .order_by(desc(IntercompanyTransfer.id))
    )
    return list((await session.execute(stmt)).scalars().all())

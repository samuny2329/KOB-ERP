"""HTTP routes for the sales module."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.sales.models import Customer, Delivery, DeliveryLine, SalesOrder, SoLine
from backend.modules.sales.schemas import (
    CustomerCreate,
    CustomerRead,
    DeliveryCreate,
    DeliveryRead,
    SalesOrderCreate,
    SalesOrderRead,
)

router = APIRouter(prefix="/sales", tags=["sales"])


# ── Customers ─────────────────────────────────────────────────────────


@router.get("/customers", response_model=list[CustomerRead])
async def list_customers(session: SessionDep, _user: CurrentUser) -> list[Customer]:
    rows = (
        await session.execute(
            select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code)
        )
    ).scalars().all()
    return list(rows)


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate, session: SessionDep, _user: CurrentUser
) -> Customer:
    customer = Customer(**body.model_dump())
    session.add(customer)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "customer code already exists") from exc
    return customer


@router.get("/customers/{customer_id}", response_model=CustomerRead)
async def get_customer(
    customer_id: int, session: SessionDep, _user: CurrentUser
) -> Customer:
    c = await session.get(Customer, customer_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer not found")
    return c


# ── Sales orders ──────────────────────────────────────────────────────


@router.get("/orders", response_model=list[SalesOrderRead])
async def list_sales_orders(
    session: SessionDep, _user: CurrentUser, state: str | None = None
) -> list[SalesOrder]:
    stmt = (
        select(SalesOrder)
        .where(SalesOrder.deleted_at.is_(None))
        .options(selectinload(SalesOrder.lines))
        .order_by(SalesOrder.created_at.desc())
    )
    if state:
        stmt = stmt.where(SalesOrder.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/orders", response_model=SalesOrderRead, status_code=status.HTTP_201_CREATED)
async def create_sales_order(
    body: SalesOrderCreate, session: SessionDep, _user: CurrentUser
) -> SalesOrder:
    data = body.model_dump(exclude={"lines"})
    so = SalesOrder(**data)
    session.add(so)
    await session.flush()
    subtotal = 0.0
    for ld in body.lines:
        line = SoLine(order_id=so.id, **ld.model_dump())
        disc = (ld.discount_pct or 0) / 100
        line.subtotal = round(ld.qty_ordered * ld.unit_price * (1 - disc), 2)
        subtotal += line.subtotal
        session.add(line)
    so.subtotal = subtotal
    so.total_amount = subtotal - so.discount_amount + so.tax_amount
    await session.flush()
    await session.refresh(so, ["lines"])
    return so


@router.post("/orders/{so_id}/confirm", response_model=SalesOrderRead)
async def confirm_so(so_id: int, session: SessionDep, _user: CurrentUser) -> SalesOrder:
    so = await session.get(SalesOrder, so_id)
    if not so:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SO not found")
    if so.state != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot confirm SO in state {so.state!r}")
    so.state = "confirmed"
    so.confirmed_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(so, ["lines"])
    return so


@router.post("/orders/{so_id}/cancel", response_model=SalesOrderRead)
async def cancel_so(so_id: int, session: SessionDep, _user: CurrentUser) -> SalesOrder:
    so = await session.get(SalesOrder, so_id)
    if not so:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SO not found")
    if so.state in ("shipped", "invoiced"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot cancel SO in state {so.state!r}")
    so.state = "cancelled"
    await session.flush()
    await session.refresh(so, ["lines"])
    return so


# ── Deliveries ────────────────────────────────────────────────────────


@router.get("/deliveries", response_model=list[DeliveryRead])
async def list_deliveries(
    session: SessionDep, _user: CurrentUser, so_id: int | None = None
) -> list[Delivery]:
    stmt = (
        select(Delivery)
        .where(Delivery.deleted_at.is_(None))
        .options(selectinload(Delivery.lines))
        .order_by(Delivery.created_at.desc())
    )
    if so_id:
        stmt = stmt.where(Delivery.sales_order_id == so_id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/deliveries", response_model=DeliveryRead, status_code=status.HTTP_201_CREATED)
async def create_delivery(
    body: DeliveryCreate, session: SessionDep, _user: CurrentUser
) -> Delivery:
    data = body.model_dump(exclude={"lines"})
    delivery = Delivery(**data)
    session.add(delivery)
    await session.flush()
    for ld in body.lines:
        session.add(DeliveryLine(delivery_id=delivery.id, **ld.model_dump()))
    await session.flush()
    await session.refresh(delivery, ["lines"])
    return delivery


@router.post("/deliveries/{delivery_id}/validate", response_model=DeliveryRead)
async def validate_delivery(
    delivery_id: int, session: SessionDep, _user: CurrentUser
) -> Delivery:
    delivery = await session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "delivery not found")
    if delivery.state != "confirmed":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"cannot validate delivery in state {delivery.state!r}"
        )
    delivery.state = "done"
    delivery.shipped_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(delivery, ["lines"])
    return delivery

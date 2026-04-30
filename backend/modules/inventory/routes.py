"""HTTP routes for the inventory module."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.inventory.models import (
    TRANSFER_DIRECTIONS,
    StockQuant,
    Transfer,
    TransferType,
)
from backend.modules.inventory.schemas import (
    StockQuantRead,
    TransferCreate,
    TransferRead,
    TransferTypeCreate,
    TransferTypeRead,
)
from backend.modules.inventory.service import (
    cancel_transfer,
    complete_transfer,
    confirm_transfer,
    create_transfer_with_lines,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


# ── Stock quants ───────────────────────────────────────────────────────


@router.get("/stock-quants", response_model=list[StockQuantRead])
async def list_quants(
    session: SessionDep,
    _user: CurrentUser,
    location_id: int | None = None,
    product_id: int | None = None,
) -> list[StockQuant]:
    stmt = select(StockQuant).where(StockQuant.deleted_at.is_(None))
    if location_id is not None:
        stmt = stmt.where(StockQuant.location_id == location_id)
    if product_id is not None:
        stmt = stmt.where(StockQuant.product_id == product_id)
    return list((await session.execute(stmt)).scalars().all())


# ── Transfer types ─────────────────────────────────────────────────────


@router.post(
    "/transfer-types", response_model=TransferTypeRead, status_code=status.HTTP_201_CREATED
)
async def create_transfer_type(
    body: TransferTypeCreate, session: SessionDep, _user: CurrentUser
) -> TransferType:
    if body.direction not in TRANSFER_DIRECTIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid direction: {body.direction}")
    tt = TransferType(
        warehouse_id=body.warehouse_id,
        code=body.code,
        name=body.name,
        direction=body.direction,
        sequence_prefix=body.sequence_prefix,
        default_source_location_id=body.default_source_location_id,
        default_dest_location_id=body.default_dest_location_id,
    )
    session.add(tt)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "transfer type code already exists") from exc
    return tt


@router.get("/transfer-types", response_model=list[TransferTypeRead])
async def list_transfer_types(
    session: SessionDep,
    _user: CurrentUser,
    warehouse_id: int | None = None,
) -> list[TransferType]:
    stmt = select(TransferType).where(TransferType.deleted_at.is_(None))
    if warehouse_id is not None:
        stmt = stmt.where(TransferType.warehouse_id == warehouse_id)
    return list((await session.execute(stmt.order_by(TransferType.code))).scalars().all())


# ── Transfers ──────────────────────────────────────────────────────────


@router.post("/transfers", response_model=TransferRead, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    body: TransferCreate, session: SessionDep, _user: CurrentUser
) -> Transfer:
    tt = await session.get(TransferType, body.transfer_type_id)
    if tt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transfer type not found")

    transfer = await create_transfer_with_lines(
        session,
        transfer_type=tt,
        source_location_id=body.source_location_id,
        dest_location_id=body.dest_location_id,
        origin=body.origin,
        scheduled_date=body.scheduled_date,
        note=body.note,
        lines_data=[line.model_dump() for line in body.lines],
    )
    return transfer


@router.get("/transfers", response_model=list[TransferRead])
async def list_transfers(
    session: SessionDep,
    _user: CurrentUser,
    state: str | None = None,
    transfer_type_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Transfer]:
    stmt = (
        select(Transfer)
        .where(Transfer.deleted_at.is_(None))
        .options(selectinload(Transfer.lines))
        .order_by(Transfer.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if state is not None:
        stmt = stmt.where(Transfer.state == state)
    if transfer_type_id is not None:
        stmt = stmt.where(Transfer.transfer_type_id == transfer_type_id)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/transfers/{transfer_id}", response_model=TransferRead)
async def get_transfer(
    transfer_id: int, session: SessionDep, _user: CurrentUser
) -> Transfer:
    stmt = (
        select(Transfer)
        .where(Transfer.id == transfer_id)
        .options(selectinload(Transfer.lines))
    )
    transfer = (await session.execute(stmt)).scalar_one_or_none()
    if transfer is None or transfer.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transfer not found")
    return transfer


@router.post("/transfers/{transfer_id}/confirm", response_model=TransferRead)
async def post_confirm_transfer(
    transfer_id: int, session: SessionDep, _user: CurrentUser
) -> Transfer:
    transfer = await get_transfer(transfer_id, session, _user)
    return await confirm_transfer(session, transfer)


@router.post("/transfers/{transfer_id}/done", response_model=TransferRead)
async def post_done_transfer(
    transfer_id: int, session: SessionDep, _user: CurrentUser
) -> Transfer:
    transfer = await get_transfer(transfer_id, session, _user)
    return await complete_transfer(session, transfer)


@router.post("/transfers/{transfer_id}/cancel", response_model=TransferRead)
async def post_cancel_transfer(
    transfer_id: int, session: SessionDep, _user: CurrentUser
) -> Transfer:
    transfer = await get_transfer(transfer_id, session, _user)
    return await cancel_transfer(session, transfer)

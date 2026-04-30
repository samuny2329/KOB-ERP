"""HTTP routes for the accounting module."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.auth import CurrentUser
from backend.core.db import SessionDep
from backend.modules.accounting.models import (
    Account,
    Journal,
    JournalEntry,
    JournalEntryLine,
    TaxRate,
)
from backend.modules.accounting.schemas import (
    AccountCreate,
    AccountRead,
    JournalCreate,
    JournalEntryCreate,
    JournalEntryRead,
    JournalRead,
    TaxRateCreate,
    TaxRateRead,
)

router = APIRouter(prefix="/accounting", tags=["accounting"])


# ── Chart of accounts ─────────────────────────────────────────────────


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(
    session: SessionDep, _user: CurrentUser, account_type: str | None = None
) -> list[Account]:
    stmt = select(Account).where(Account.deleted_at.is_(None)).order_by(Account.code)
    if account_type:
        stmt = stmt.where(Account.account_type == account_type)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate, session: SessionDep, _user: CurrentUser
) -> Account:
    acc = Account(**body.model_dump())
    session.add(acc)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "account code already exists") from exc
    return acc


# ── Journals ──────────────────────────────────────────────────────────


@router.get("/journals", response_model=list[JournalRead])
async def list_journals(session: SessionDep, _user: CurrentUser) -> list[Journal]:
    rows = (
        await session.execute(select(Journal).where(Journal.deleted_at.is_(None)).order_by(Journal.code))
    ).scalars().all()
    return list(rows)


@router.post("/journals", response_model=JournalRead, status_code=status.HTTP_201_CREATED)
async def create_journal(
    body: JournalCreate, session: SessionDep, _user: CurrentUser
) -> Journal:
    journal = Journal(**body.model_dump())
    session.add(journal)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "journal code already exists") from exc
    return journal


# ── Journal entries ───────────────────────────────────────────────────


@router.get("/entries", response_model=list[JournalEntryRead])
async def list_entries(
    session: SessionDep,
    _user: CurrentUser,
    journal_id: int | None = None,
    state: str | None = None,
) -> list[JournalEntry]:
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.deleted_at.is_(None))
        .options(selectinload(JournalEntry.lines))
        .order_by(JournalEntry.entry_date.desc())
    )
    if journal_id:
        stmt = stmt.where(JournalEntry.journal_id == journal_id)
    if state:
        stmt = stmt.where(JournalEntry.state == state)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/entries", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: JournalEntryCreate, session: SessionDep, _user: CurrentUser
) -> JournalEntry:
    lines_data = body.lines
    total_debit = sum(l.debit for l in lines_data)
    total_credit = sum(l.credit for l in lines_data)
    if round(total_debit, 2) != round(total_credit, 2):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"unbalanced entry: debit={total_debit} credit={total_credit}",
        )
    data = body.model_dump(exclude={"lines"})
    entry = JournalEntry(**data)
    session.add(entry)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "entry number already exists") from exc
    for ld in lines_data:
        session.add(JournalEntryLine(entry_id=entry.id, **ld.model_dump()))
    await session.flush()
    await session.refresh(entry, ["lines"])
    return entry


@router.post("/entries/{entry_id}/post", response_model=JournalEntryRead)
async def post_entry(entry_id: int, session: SessionDep, _user: CurrentUser) -> JournalEntry:
    entry = await session.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    if entry.state != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"cannot post entry in state {entry.state!r}"
        )
    entry.state = "posted"
    entry.posted_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(entry, ["lines"])
    return entry


@router.post("/entries/{entry_id}/cancel", response_model=JournalEntryRead)
async def cancel_entry(entry_id: int, session: SessionDep, _user: CurrentUser) -> JournalEntry:
    entry = await session.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    if entry.state != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "can only cancel draft entries"
        )
    entry.state = "cancelled"
    await session.flush()
    await session.refresh(entry, ["lines"])
    return entry


# ── Tax rates ─────────────────────────────────────────────────────────


@router.get("/tax-rates", response_model=list[TaxRateRead])
async def list_tax_rates(session: SessionDep, _user: CurrentUser) -> list[TaxRate]:
    rows = (
        await session.execute(select(TaxRate).where(TaxRate.deleted_at.is_(None)).order_by(TaxRate.code))
    ).scalars().all()
    return list(rows)


@router.post("/tax-rates", response_model=TaxRateRead, status_code=status.HTTP_201_CREATED)
async def create_tax_rate(
    body: TaxRateCreate, session: SessionDep, _user: CurrentUser
) -> TaxRate:
    tax = TaxRate(**body.model_dump())
    session.add(tax)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "tax code already exists") from exc
    return tax

"""Hash-chain activity log — tamper-evident audit trail of operational events.

Each ``ActivityLog`` row stores a SHA-256 ``block_hash`` over its content
plus the previous row's ``block_hash`` (linked-list style).  Verifying
the chain == recomputing every block_hash and confirming it still
matches: any tampered row breaks every subsequent hash.

Lives in the ``core`` schema because every module emits into it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.base_model import CoreModel


class ActivityLog(CoreModel):
    """Append-only operational event with cryptographic chain link."""

    __tablename__ = "activity_log"
    __table_args__ = ({"schema": "core"},)

    actor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("core.user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    ref: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    block_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


def compute_block_hash(
    *,
    actor_id: int | None,
    action: str,
    ref: str | None,
    code: str | None,
    note: str | None,
    occurred_at: datetime,
    prev_hash: str | None,
) -> str:
    """SHA-256 over a canonical JSON serialization of every field + prev_hash.

    The use of ``sort_keys=True`` + ``separators`` produces a stable
    representation that's easy to re-derive in tests and audits.
    """
    payload: dict[str, Any] = {
        "actor_id": actor_id,
        "action": action,
        "ref": ref,
        "code": code,
        "note": note,
        "occurred_at": occurred_at.isoformat(),
        "prev_hash": prev_hash,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def append_activity(
    session: AsyncSession,
    *,
    actor_id: int | None,
    action: str,
    ref: str | None = None,
    code: str | None = None,
    note: str | None = None,
) -> ActivityLog:
    """Add a new ActivityLog linked to the most recent row's block_hash.

    The chain is global (single sequence across all actors / actions);
    if KOB needs per-actor chains later, partition by ``actor_id``.
    """
    from sqlalchemy import desc, select

    stmt = select(ActivityLog).order_by(desc(ActivityLog.id)).limit(1)
    last = (await session.execute(stmt)).scalar_one_or_none()
    prev_hash = last.block_hash if last is not None else None

    occurred_at = datetime.now(UTC)
    block_hash = compute_block_hash(
        actor_id=actor_id,
        action=action,
        ref=ref,
        code=code,
        note=note,
        occurred_at=occurred_at,
        prev_hash=prev_hash,
    )
    row = ActivityLog(
        actor_id=actor_id,
        action=action,
        ref=ref,
        code=code,
        note=note,
        occurred_at=occurred_at,
        prev_hash=prev_hash,
        block_hash=block_hash,
    )
    session.add(row)
    await session.flush()
    return row


async def verify_chain(session: AsyncSession) -> tuple[bool, int | None]:
    """Re-derive every block_hash and confirm the chain is intact.

    Returns ``(True, None)`` if the entire chain is valid.  Otherwise
    returns ``(False, broken_id)`` pointing at the first row whose stored
    ``block_hash`` doesn't match the recomputed value.
    """
    from sqlalchemy import select

    rows = (
        (await session.execute(select(ActivityLog).order_by(ActivityLog.id))).scalars().all()
    )
    prev: str | None = None
    for row in rows:
        expected = compute_block_hash(
            actor_id=row.actor_id,
            action=row.action,
            ref=row.ref,
            code=row.code,
            note=row.note,
            occurred_at=row.occurred_at,
            prev_hash=prev,
        )
        if expected != row.block_hash or row.prev_hash != prev:
            return False, row.id
        prev = row.block_hash
    return True, None

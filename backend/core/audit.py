"""Audit logging — write a row to ``core.audit_log`` for every mutation.

Two layers:

1. **SQLAlchemy event hook** (``after_flush``) captures create/update/delete
   on any model derived from BaseModel and stages an AuditLog row.  Captures
   only the changed columns (diff).

2. **Request middleware** stores the current request id + actor id in a
   ContextVar so the hook can stamp them onto the log row.
"""

from __future__ import annotations

import contextvars
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from backend.core.models import AuditLog

_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "audit_request_id", default=None
)
_actor_id_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "audit_actor_id", default=None
)


def set_audit_context(request_id: str | None, actor_id: int | None) -> None:
    _request_id_ctx.set(request_id)
    _actor_id_ctx.set(actor_id)


def _jsonable(value: Any) -> Any:
    """Coerce Python values into something json.dumps can swallow.

    SQLAlchemy hands us datetimes / Decimals / dates; the JSON column
    encoder doesn't know what to do with them, so we stringify here.
    """
    import datetime as _dt
    import decimal as _dc
    import enum as _enum
    import uuid as _uuid

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, _dc.Decimal):
        return float(value)
    if isinstance(value, _uuid.UUID):
        return str(value)
    if isinstance(value, _enum.Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def _diff_changed(obj: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (before, after) dicts of columns whose value changed."""
    inspected = inspect(obj)
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for attr in inspected.mapper.column_attrs:
        history = getattr(inspected.attrs, attr.key).history
        if history.has_changes():
            before[attr.key] = _jsonable(history.deleted[0]) if history.deleted else None
            after[attr.key] = _jsonable(history.added[0]) if history.added else None
    return before, after


def _model_path(obj: Any) -> str:
    cls = type(obj)
    return f"{cls.__module__.rsplit('.', 1)[-1]}.{cls.__name__}"


def register_audit_hooks() -> None:
    """Attach SQLAlchemy event listeners.  Call once at startup."""

    @event.listens_for(Session, "after_flush")
    def _after_flush(session: Session, _flush_context: Any) -> None:
        # Skip if we're already writing AuditLog rows — prevent recursion.
        new_logs: list[AuditLog] = []

        for obj in session.new:
            if isinstance(obj, AuditLog):
                continue
            new_logs.append(
                AuditLog(
                    actor_id=_actor_id_ctx.get(),
                    model=_model_path(obj),
                    record_id=getattr(obj, "id", None),
                    action="create",
                    before=None,
                    after=_diff_changed(obj)[1],
                    request_id=_request_id_ctx.get(),
                )
            )

        for obj in session.dirty:
            if isinstance(obj, AuditLog) or not session.is_modified(obj):
                continue
            before, after = _diff_changed(obj)
            if not before and not after:
                continue
            new_logs.append(
                AuditLog(
                    actor_id=_actor_id_ctx.get(),
                    model=_model_path(obj),
                    record_id=getattr(obj, "id", None),
                    action="update",
                    before=before,
                    after=after,
                    request_id=_request_id_ctx.get(),
                )
            )

        for obj in session.deleted:
            if isinstance(obj, AuditLog):
                continue
            new_logs.append(
                AuditLog(
                    actor_id=_actor_id_ctx.get(),
                    model=_model_path(obj),
                    record_id=getattr(obj, "id", None),
                    action="delete",
                    before=_diff_changed(obj)[0] or None,
                    after=None,
                    request_id=_request_id_ctx.get(),
                )
            )

        for log in new_logs:
            session.add(log)


# ── ASGI middleware ────────────────────────────────────────────────────


Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


async def request_id_middleware(
    scope: dict[str, Any],
    receive: Receive,
    send: Send,
    app: Callable[[dict, Receive, Send], Awaitable[None]],
) -> None:
    """Pure ASGI middleware that stamps a request id on every request."""
    if scope["type"] != "http":
        await app(scope, receive, send)
        return

    request_id = uuid.uuid4().hex[:16]
    set_audit_context(request_id, None)

    async def send_with_header(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            headers = list(message.get("headers", []))
            headers.append((b"x-request-id", request_id.encode()))
            message["headers"] = headers
        await send(message)

    await app(scope, receive, send_with_header)

"""In-memory pub/sub event bus.

Modules register handlers at import time::

    from backend.core.events import on, emit

    @on("inventory.transfer.confirmed")
    async def reserve_stock(event: dict) -> None:
        ...

    await emit("inventory.transfer.confirmed", {"transfer_id": 42})

This is intentionally tiny — when we need cross-process delivery, the same
API is preserved and the bus swaps to Redis pub/sub or Celery tasks.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias

EventPayload: TypeAlias = dict[str, Any]
Handler: TypeAlias = Callable[[EventPayload], Awaitable[None]]

_log = logging.getLogger(__name__)
_handlers: dict[str, list[Handler]] = defaultdict(list)


def on(event_name: str) -> Callable[[Handler], Handler]:
    """Register an async handler for ``event_name``.  Decorator form."""

    def _register(handler: Handler) -> Handler:
        _handlers[event_name].append(handler)
        return handler

    return _register


async def emit(event_name: str, payload: EventPayload) -> None:
    """Fan out ``payload`` to every registered handler concurrently.

    Handler exceptions are logged but never propagate — one bad subscriber
    must not block the rest of the system.
    """
    handlers = _handlers.get(event_name, [])
    if not handlers:
        return

    results = await asyncio.gather(
        *(handler(payload) for handler in handlers),
        return_exceptions=True,
    )
    for handler, result in zip(handlers, results, strict=True):
        if isinstance(result, Exception):
            _log.exception(
                "event handler %s raised on %r", handler.__qualname__, event_name,
                exc_info=result,
            )


def clear() -> None:
    """Test-only — wipe all handlers."""
    _handlers.clear()

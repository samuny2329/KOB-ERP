"""Generic state-machine mixin for documents that flow draft → confirmed → done.

Each domain model that needs a workflow inherits ``WorkflowMixin`` and sets
``allowed_transitions`` to declare which moves are legal.  ``transition()``
performs the move atomically and raises if illegal.

Concrete subclass example::

    class Transfer(BaseModel, WorkflowMixin):
        __tablename__ = "transfer"
        allowed_transitions = {
            "draft": {"confirmed", "cancelled"},
            "confirmed": {"done", "cancelled"},
            "done": set(),
            "cancelled": set(),
        }
"""

from __future__ import annotations

from typing import ClassVar

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class WorkflowError(Exception):
    """Raised when an illegal state transition is attempted."""


# Sentinel default — concrete models must override.
DEFAULT_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"done", "cancelled"},
    "done": set(),
    "cancelled": set(),
}


class WorkflowMixin:
    """Adds a ``state`` column and ``transition()`` method.

    The mixin holds the column declaration only; transition rules live on
    the concrete model so each module can customise them.
    """

    allowed_transitions: ClassVar[dict[str, set[str]]] = DEFAULT_TRANSITIONS
    initial_state: ClassVar[str] = "draft"

    state: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="draft",
        index=True,
    )

    def transition(self, target: str) -> None:
        """Move to ``target`` if allowed by ``allowed_transitions``.

        Raises ``WorkflowError`` for an illegal move.  Does NOT commit — the
        caller's session is responsible for persistence.
        """
        legal = self.allowed_transitions.get(self.state, set())
        if target not in legal:
            raise WorkflowError(
                f"illegal transition {self.state!r} → {target!r}"
                f" (allowed: {sorted(legal) or '∅'})"
            )
        self.state = target

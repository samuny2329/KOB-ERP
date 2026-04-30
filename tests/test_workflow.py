from __future__ import annotations

import pytest

from backend.core.workflow import WorkflowError, WorkflowMixin


class _Doc(WorkflowMixin):
    """Plain in-memory stand-in (no SQLAlchemy mapping) for unit testing."""

    allowed_transitions = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }

    def __init__(self) -> None:
        self.state = "draft"


def test_legal_transition() -> None:
    doc = _Doc()
    doc.transition("confirmed")
    assert doc.state == "confirmed"
    doc.transition("done")
    assert doc.state == "done"


def test_illegal_transition_raises() -> None:
    doc = _Doc()
    with pytest.raises(WorkflowError):
        doc.transition("done")  # draft → done is illegal


def test_terminal_state_cannot_move() -> None:
    doc = _Doc()
    doc.transition("cancelled")
    with pytest.raises(WorkflowError):
        doc.transition("confirmed")

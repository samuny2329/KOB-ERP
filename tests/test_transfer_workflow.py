"""Tests for the inventory.Transfer state machine."""

from backend.modules.inventory.models import Transfer


def test_transfer_allowed_transitions_match_spec() -> None:
    """Confirm the state machine spec from docs/ROADMAP."""
    assert Transfer.allowed_transitions == {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }


def test_transfer_inherits_workflow_mixin() -> None:
    from backend.core.workflow import WorkflowMixin

    assert issubclass(Transfer, WorkflowMixin)

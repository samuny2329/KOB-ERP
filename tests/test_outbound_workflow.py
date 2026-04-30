"""State-machine + activity-log tests for the outbound module."""

from datetime import UTC, datetime

import pytest

from backend.core.models_audit import compute_block_hash
from backend.core.workflow import WorkflowMixin
from backend.modules.outbound.models import DispatchBatch, Order


def test_order_inherits_workflow_mixin() -> None:
    assert issubclass(Order, WorkflowMixin)


def test_order_state_flow_is_complete() -> None:
    flow = Order.allowed_transitions
    assert "picking" in flow["pending"]
    assert "picked" in flow["picking"]
    assert "packing" in flow["picked"]
    assert "packed" in flow["packing"]
    assert "shipped" in flow["packed"]
    # cancelled reachable from every non-terminal state
    for src in ("pending", "picking", "picked", "packing", "packed"):
        assert "cancelled" in flow[src]
    # terminal
    assert flow["shipped"] == set()
    assert flow["cancelled"] == set()


def test_dispatch_batch_state_flow() -> None:
    flow = DispatchBatch.allowed_transitions
    assert flow["draft"] == {"scanning", "cancelled"}
    assert flow["scanning"] == {"dispatched", "cancelled"}
    assert flow["dispatched"] == set()
    assert flow["cancelled"] == set()


def test_block_hash_is_deterministic() -> None:
    when = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)
    h1 = compute_block_hash(
        actor_id=1, action="order.picked", ref="SO-1", code="42", note=None,
        occurred_at=when, prev_hash=None,
    )
    h2 = compute_block_hash(
        actor_id=1, action="order.picked", ref="SO-1", code="42", note=None,
        occurred_at=when, prev_hash=None,
    )
    assert h1 == h2
    assert len(h1) == 64


def test_block_hash_changes_with_prev() -> None:
    when = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)
    args = dict(actor_id=1, action="x", ref="y", code=None, note=None, occurred_at=when)
    a = compute_block_hash(**args, prev_hash=None)
    b = compute_block_hash(**args, prev_hash=a)
    assert a != b


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor_id", 99),
        ("action", "different"),
        ("ref", "OTHER"),
        ("note", "tampered"),
    ],
)
def test_block_hash_changes_when_any_field_changes(field: str, value: object) -> None:
    when = datetime(2026, 4, 30, 12, 0, 0, tzinfo=UTC)
    base = dict(
        actor_id=1, action="order.picked", ref="SO-1",
        code="42", note=None, occurred_at=when, prev_hash=None,
    )
    h1 = compute_block_hash(**base)
    tampered = {**base, field: value}
    h2 = compute_block_hash(**tampered)
    assert h1 != h2

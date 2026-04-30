"""State-machine spec tests for Phase 2c (counts + quality)."""

from backend.core.workflow import WorkflowMixin
from backend.modules.inventory.models_count import CountSession, CountTask
from backend.modules.quality.models import Check


def test_count_session_inherits_workflow_mixin() -> None:
    assert issubclass(CountSession, WorkflowMixin)


def test_count_session_state_flow() -> None:
    assert CountSession.allowed_transitions == {
        "draft": {"in_progress", "cancelled"},
        "in_progress": {"reconciling", "cancelled"},
        "reconciling": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }


def test_count_task_state_flow_supports_recount() -> None:
    flow = CountTask.allowed_transitions
    # Auditor can return submitted-task back to counting (recount).
    assert "counting" in flow["submitted"]
    # Verifier can revert verified→submitted.
    assert "submitted" in flow["verified"]
    # Approved is terminal.
    assert flow["approved"] == set()


def test_quality_check_state_flow_is_terminal_after_decision() -> None:
    assert Check.allowed_transitions == {
        "pending": {"passed", "failed", "skipped"},
        "passed": set(),
        "failed": set(),
        "skipped": set(),
    }

import pytest

from app.core.errors import IllegalTransitionError
from app.core.state_machine import FlowStatus, assert_legal_transition, is_legal_transition


def test_happy_path_is_fully_legal():
    path = [
        FlowStatus.DRAFT,
        FlowStatus.PLAN_PENDING_APPROVAL,
        FlowStatus.PLAN_APPROVED,
        FlowStatus.PREVIEW_PENDING_APPROVAL,
        FlowStatus.APPROVED,
        FlowStatus.RUNNING,
        FlowStatus.PUBLISHED,
    ]
    for current, target in zip(path, path[1:]):
        assert is_legal_transition(current, target)
        assert_legal_transition(current, target)  # must not raise


def test_editing_plan_is_a_legal_self_loop():
    assert is_legal_transition(
        FlowStatus.PLAN_PENDING_APPROVAL, FlowStatus.PLAN_PENDING_APPROVAL
    )


def test_rejecting_preview_returns_to_plan_editing():
    assert is_legal_transition(
        FlowStatus.PREVIEW_PENDING_APPROVAL, FlowStatus.PLAN_PENDING_APPROVAL
    )


def test_cannot_skip_straight_to_execute_from_draft():
    assert not is_legal_transition(FlowStatus.DRAFT, FlowStatus.RUNNING)
    with pytest.raises(IllegalTransitionError):
        assert_legal_transition(FlowStatus.DRAFT, FlowStatus.RUNNING)


def test_cannot_run_without_preview_approval():
    # PLAN_APPROVED must go through PREVIEW_PENDING_APPROVAL / APPROVED first
    assert not is_legal_transition(FlowStatus.PLAN_APPROVED, FlowStatus.RUNNING)


def test_cannot_reenter_plan_editing_from_published():
    assert not is_legal_transition(FlowStatus.PUBLISHED, FlowStatus.PLAN_PENDING_APPROVAL)


def test_failed_run_can_be_retried_from_either_approval_stage():
    assert is_legal_transition(FlowStatus.FAILED, FlowStatus.PLAN_PENDING_APPROVAL)
    assert is_legal_transition(FlowStatus.FAILED, FlowStatus.PREVIEW_PENDING_APPROVAL)


def test_illegal_transition_error_carries_both_states():
    with pytest.raises(IllegalTransitionError) as exc_info:
        assert_legal_transition(FlowStatus.DRAFT, FlowStatus.PUBLISHED)
    assert exc_info.value.current_status == "draft"
    assert exc_info.value.target_status == "published"

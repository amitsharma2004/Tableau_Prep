"""Explicit state machine for a Flow's human-in-the-loop lifecycle.

Only `app.services.flow_service` is allowed to call `transition()`. API routes
must never assign `flow.status` directly - that would bypass the approval
gates this module exists to enforce (e.g. `/execute` becoming reachable
without a recorded preview approval).
"""
from __future__ import annotations

from enum import Enum


class FlowStatus(str, Enum):
    DRAFT = "draft"
    PLAN_PENDING_APPROVAL = "plan_pending_approval"
    PLAN_APPROVED = "plan_approved"
    PREVIEW_PENDING_APPROVAL = "preview_pending_approval"
    APPROVED = "approved"  # preview approved, ready for full execute
    RUNNING = "running"
    PUBLISHED = "published"
    FAILED = "failed"


# Adjacency list of legal transitions. A self-loop on PLAN_PENDING_APPROVAL
# represents a human editing the plan (new plan_versions row, same status).
TRANSITIONS: dict[FlowStatus, set[FlowStatus]] = {
    FlowStatus.DRAFT: {FlowStatus.PLAN_PENDING_APPROVAL},
    FlowStatus.PLAN_PENDING_APPROVAL: {
        FlowStatus.PLAN_PENDING_APPROVAL,
        FlowStatus.PLAN_APPROVED,
    },
    FlowStatus.PLAN_APPROVED: {
        FlowStatus.PREVIEW_PENDING_APPROVAL,
    },
    FlowStatus.PREVIEW_PENDING_APPROVAL: {
        FlowStatus.APPROVED,
        FlowStatus.PLAN_PENDING_APPROVAL,  # preview rejected or revised via chat
    },
    FlowStatus.APPROVED: {
        FlowStatus.RUNNING,
        FlowStatus.PLAN_PENDING_APPROVAL,  # User updates plan before/after running
    },
    FlowStatus.RUNNING: {FlowStatus.PUBLISHED, FlowStatus.FAILED},
    FlowStatus.FAILED: {
        FlowStatus.PLAN_PENDING_APPROVAL,
        FlowStatus.PREVIEW_PENDING_APPROVAL,
        FlowStatus.RUNNING,  # Allow re-running an approved flow if it failed transiently
    },
    FlowStatus.PUBLISHED: {
        FlowStatus.RUNNING,  # Allow scheduled or manual re-executions of an already approved & published flow
        FlowStatus.PLAN_PENDING_APPROVAL,  # Allow editing plan after publishing
    },
}


def is_legal_transition(current: FlowStatus, target: FlowStatus) -> bool:
    return target in TRANSITIONS.get(current, set())


def assert_legal_transition(current: FlowStatus, target: FlowStatus) -> None:
    from app.core.errors import IllegalTransitionError

    if not is_legal_transition(current, target):
        raise IllegalTransitionError(current.value, target.value)

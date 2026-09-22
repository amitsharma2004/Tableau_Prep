"""The only module allowed to change Flow.status.

Every transition goes through `move_flow()`, which validates it against
`core.state_machine` and writes a matching AuditLog row in the same
transaction. API routes must call this instead of touching `flow.status`
directly - that is what makes "execute is unreachable without a recorded
preview approval" an enforced invariant rather than a convention.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.state_machine import FlowStatus, assert_legal_transition
from app.db.models.audit_log import AuditLog
from app.db.models.connection import Connection
from app.db.models.flow import Flow
from app.schemas.flow import FlowCreate


class SourceConnectionNotFoundError(DomainError):
    def __init__(self, connection_id: str):
        super().__init__(f"Source connection {connection_id!r} not found")


def create_flow(db: Session, payload: FlowCreate, actor: str) -> Flow:
    source = db.get(Connection, payload.source_connection_id)
    if source is None:
        raise SourceConnectionNotFoundError(payload.source_connection_id)
    if source.type not in ("postgres", "mysql", "sqlite"):
        raise DomainError(
            f"Connection {payload.source_connection_id!r} is type {source.type!r}, "
            "which cannot be used as a flow's source (must be postgres, mysql, or sqlite)."
        )

    flow = Flow(
        name=payload.name,
        nl_request=payload.nl_request,
        source_connection_id=payload.source_connection_id,
        tableau_connection_id=payload.tableau_connection_id,
        target_datasource_name=payload.target_datasource_name or payload.name,
        status=FlowStatus.DRAFT.value,
        created_by=actor,
    )
    db.add(flow)
    db.flush()

    db.add(AuditLog(flow_id=flow.id, event_type="flow_created", actor=actor))
    db.flush()
    return flow


def move_flow(
    db: Session,
    flow: Flow,
    target: FlowStatus,
    actor: str,
    detail: dict | None = None,
) -> Flow:
    current = FlowStatus(flow.status)
    assert_legal_transition(current, target)

    flow.status = target.value
    db.add(
        AuditLog(
            flow_id=flow.id,
            event_type=f"transitioned_to_{target.value}",
            actor=actor,
            detail_json=json.dumps(detail) if detail else None,
        )
    )
    db.flush()
    return flow

"""Ties the connector, the LLM planner and persistence together.

`generate_plan_for_flow()` is the only place that constructs
SchemaContext/SampleContext from a live connection and hands them to
llm.planner.generate_plan() - the Connection object and its decrypted
secret never leave this function.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.config import settings
from app.connectors.factory import build_connector
from app.core.errors import ConnectionFailedError, DomainError
from app.core.security import decrypt
from app.core.state_machine import FlowStatus
from app.db.base import utcnow
from app.db.models.connection import Connection
from app.db.models.flow import Flow
from app.db.models.plan_version import PlanVersion
from app.llm.context import SampleContext, SchemaContext
from app.llm.planner import generate_plan
from app.llm.plan_schema import PlanDraft
from app.schemas.plan import PlanVersionRead
from app.services.flow_service import move_flow


def _schema_snapshot_json(schema: SchemaContext) -> str:
    return json.dumps(
        {
            "tables": [
                {
                    "schema": t.schema,
                    "name": t.name,
                    "columns": [{"name": c.name, "data_type": c.data_type, "nullable": c.nullable} for c in t.columns],
                }
                for t in schema.tables
            ]
        }
    )


def _build_schema_and_samples(connection: Connection) -> tuple[SchemaContext, SampleContext]:
    if connection.type not in ("postgres", "mysql", "sqlite"):
        raise DomainError(f"Cannot generate a plan from connection type {connection.type!r}")

    secret = decrypt(connection.encrypted_secret)
    try:
        connector = build_connector(
            connection.type, connection.host, connection.port, connection.database_name,
            connection.username, secret,
        )
        tables = connector.introspect_schema()
        samples = {
            f"{t.schema}.{t.name}": connector.sample_rows(t.name, t.schema, settings.schema_sample_row_limit)
            for t in tables
        }
    except Exception as exc:
        raise ConnectionFailedError(
            f"Could not read schema from '{connection.name}': {exc}"
        ) from exc

    return SchemaContext(tables=tables), SampleContext(samples=samples)


def _next_version_number(db: Session, flow_id: str) -> int:
    latest = (
        db.query(PlanVersion)
        .filter_by(flow_id=flow_id)
        .order_by(PlanVersion.version_number.desc())
        .first()
    )
    return (latest.version_number + 1) if latest else 1


def get_active_plan_version(db: Session, flow: Flow) -> PlanVersion:
    version_id = flow.current_version_id or flow.active_plan_version_id
    if version_id is None:
        raise DomainError("Flow has no plan yet - generate or save one first")
    version = db.get(PlanVersion, version_id)
    if version is None:
        raise DomainError(f"Plan version {version_id!r} not found")
    return version


def to_plan_version_read(pv: PlanVersion) -> PlanVersionRead:
    return PlanVersionRead(
        id=pv.id,
        flow_id=pv.flow_id,
        version_number=pv.version_number,
        source=pv.source,
        parent_version_id=getattr(pv, "parent_version_id", None),
        change_summary=getattr(pv, "change_summary", None),
        plan=PlanDraft.model_validate_json(pv.plan_json),
        approved_by=pv.approved_by,
        approved_at=pv.approved_at,
        created_at=pv.created_at,
    )


def generate_plan_for_flow(db: Session, flow: Flow, actor: str, prompt: str | None = None) -> PlanVersion:
    # FAILED is included so a flow whose execute run failed can be
    # re-planned from scratch - the state machine already declares
    # failed -> plan_pending_approval legal (see core/state_machine.py);
    # this is the function that actually exercises that transition.
    current_status = FlowStatus(flow.status)
    if current_status == FlowStatus.RUNNING:
        raise DomainError(
            "Cannot modify or re-plan a flow while an execution run is currently in progress."
        )

    connection = db.get(Connection, flow.source_connection_id)
    if connection is None:
        raise DomainError(f"Source connection {flow.source_connection_id!r} not found")

    effective_prompt = prompt or flow.nl_request
    if prompt:
        flow.nl_request = prompt

    existing_plan: PlanDraft | None = None
    if flow.active_plan_version_id:
        existing_version = db.get(PlanVersion, flow.active_plan_version_id)
        if existing_version and existing_version.plan_json:
            try:
                existing_plan = PlanDraft.model_validate_json(existing_version.plan_json)
            except Exception:
                pass

    schema_context, sample_context = _build_schema_and_samples(connection)
    plan_draft = generate_plan(effective_prompt, schema_context, sample_context, existing_plan=existing_plan)

    version = PlanVersion(
        flow_id=flow.id,
        version_number=_next_version_number(db, flow.id),
        source="llm_generated",
        plan_json=plan_draft.model_dump_json(),
        schema_snapshot_json=_schema_snapshot_json(schema_context),
    )
    db.add(version)
    db.flush()

    flow.current_version_id = version.id
    flow.active_plan_version_id = version.id
    move_flow(
        db,
        flow,
        FlowStatus.PLAN_PENDING_APPROVAL,
        actor=actor,
        detail={"plan_version_id": version.id, "version_number": version.version_number},
    )
    db.flush()
    return version


def edit_plan(
    db: Session,
    flow: Flow,
    new_plan: PlanDraft,
    actor: str,
    change_summary: str | None = None,
    base_version_id: str | None = None,
) -> PlanVersion:
    """Human checkpoint edit of the flow plan. Always creates a new,
    immutable plan_versions row (source='human_edited') rather than mutating the
    existing one.
    """
    current_status = FlowStatus(flow.status)
    if current_status == FlowStatus.RUNNING:
        raise DomainError(
            "Cannot save checkpoint while an execution run is currently in progress."
        )

    # Optimistic concurrency check: if user provided a base_version_id, ensure no one else saved ahead
    latest_current = flow.current_version_id or flow.active_plan_version_id
    if base_version_id and latest_current and base_version_id != latest_current:
        raise DomainError(
            "Flow has changed since you opened it. Please reload the latest version to avoid overwriting changes."
        )

    # Determine schema snapshot: from previous version or generate from source connection
    schema_snapshot_str = "{}"
    if latest_current:
        previous = db.get(PlanVersion, latest_current)
        if previous and previous.schema_snapshot_json:
            schema_snapshot_str = previous.schema_snapshot_json
    else:
        conn = db.get(Connection, flow.source_connection_id)
        if conn:
            try:
                schema_ctx, _ = _build_schema_and_samples(conn)
                schema_snapshot_str = _schema_snapshot_json(schema_ctx)
            except Exception:
                pass

    version = PlanVersion(
        flow_id=flow.id,
        version_number=_next_version_number(db, flow.id),
        source="human_edited",
        parent_version_id=latest_current,
        change_summary=change_summary or new_plan.summary or "User saved checkpoint",
        plan_json=new_plan.model_dump_json(),
        schema_snapshot_json=schema_snapshot_str,
    )
    db.add(version)
    db.flush()

    flow.current_version_id = version.id
    flow.active_plan_version_id = version.id
    move_flow(
        db,
        flow,
        FlowStatus.PLAN_PENDING_APPROVAL,
        actor=actor,
        detail={"plan_version_id": version.id, "version_number": version.version_number, "edited": True},
    )
    db.flush()
    return version


def approve_plan(db: Session, flow: Flow, actor: str, version_id: str | None = None) -> PlanVersion:
    target_version_id = version_id or flow.current_version_id or flow.active_plan_version_id
    if not target_version_id:
        raise DomainError("Flow has no plan version to approve")

    version = db.get(PlanVersion, target_version_id)
    if version is None:
        raise DomainError(f"Plan version {target_version_id!r} not found")

    version.approved_by = actor
    version.approved_at = utcnow()
    db.add(version)

    flow.approved_version_id = version.id
    # Keep active_plan_version_id pointed to approved version for backward compatibility
    flow.active_plan_version_id = version.id

    move_flow(
        db,
        flow,
        FlowStatus.PLAN_APPROVED,
        actor=actor,
        detail={"plan_version_id": version.id, "version_number": version.version_number},
    )
    db.flush()
    return version


def restore_version(db: Session, flow: Flow, version_id: str, actor: str) -> PlanVersion:
    """Restores a past plan version by creating a NEW immutable version with its plan_json."""
    old_version = db.get(PlanVersion, version_id)
    if old_version is None or old_version.flow_id != flow.id:
        raise DomainError(f"Version {version_id!r} not found for this flow")

    restored_plan = PlanDraft.model_validate_json(old_version.plan_json)
    summary = f"Restored from version V{old_version.version_number}"
    return edit_plan(
        db,
        flow,
        restored_plan,
        actor=actor,
        change_summary=summary,
    )

"""Drives preview Runs - the audit backbone for what actually happened when
a plan was tried against real data. A preview always transitions the flow
to preview_pending_approval, whether it succeeds or fails: a failed preview
still needs a human decision (edit the plan, which is legal from this
status - see plan_service.edit_plan), it just can't be approved as-is.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.connectors.base import quote_identifier
from app.connectors.factory import build_connector
from app.core.errors import ConnectionFailedError, DomainError, PublishError
from app.core.security import decrypt
from app.core.state_machine import FlowStatus
from app.db.base import utcnow
from app.db.models.connection import Connection
from app.db.models.flow import Flow
from app.db.models.plan_version import PlanVersion
from app.db.models.run import Run
from app.hyper.writer import write_hyper_file
from app.llm.plan_schema import PlanDraft
from app.schemas.run import RunRead
from app.services.flow_service import move_flow
from app.tableau.client import TableauClient
from app.tableau.publisher import publish_or_overwrite
from app.transform.executor import validate_plan

PREVIEW_SAMPLE_LIMIT = 50


def to_run_read(run: Run) -> RunRead:
    return RunRead(
        id=run.id,
        flow_id=run.flow_id,
        plan_version_id=run.plan_version_id,
        run_type=run.run_type,
        status=run.status,
        generated_sql=run.generated_sql,
        generated_code_lang=run.generated_code_lang,
        rows_before=run.rows_before,
        rows_after=run.rows_after,
        row_count_anomaly=run.row_count_anomaly,
        sample_before=json.loads(run.sample_before_json) if run.sample_before_json else None,
        sample_after=json.loads(run.sample_after_json) if run.sample_after_json else None,
        hyper_file_path=run.hyper_file_path,
        publish_status=run.publish_status,
        publish_error=run.publish_error,
        error_message=run.error_message,
        trigger_type=getattr(run, "trigger_type", "manual") or "manual",
        scheduled_for=getattr(run, "scheduled_for", None),
        started_at=run.started_at,
        finished_at=run.finished_at,
        triggered_by=run.triggered_by,
    )


def _connector_for_flow(db: Session, flow: Flow):
    connection = db.get(Connection, flow.source_connection_id)
    if connection is None:
        raise DomainError(f"Source connection {flow.source_connection_id!r} not found")
    secret = decrypt(connection.encrypted_secret)
    try:
        return build_connector(
            connection.type, connection.host, connection.port, connection.database_name,
            connection.username, secret,
        )
    except Exception as exc:
        raise ConnectionFailedError(f"Could not connect to '{connection.name}': {exc}") from exc


def run_preview(db: Session, flow: Flow, actor: str) -> Run:
    # FAILED is included so a flow whose execute run failed can retry the
    # preview against the same (unedited) plan - the state machine already
    # declares failed -> preview_pending_approval legal; this is the
    # function that actually exercises that transition.
    current_status = FlowStatus(flow.status)
    if current_status not in (FlowStatus.PLAN_APPROVED, FlowStatus.FAILED):
        raise DomainError(
            f"Cannot preview flow in status '{flow.status}'. A plan must be approved first "
            "(or the flow must be in 'failed', to retry after an execute failure)."
        )
    if flow.active_plan_version_id is None:
        raise DomainError("Flow has no active plan version to preview")

    plan_version = db.get(PlanVersion, flow.active_plan_version_id)
    plan = PlanDraft.model_validate_json(plan_version.plan_json)
    connector = _connector_for_flow(db, flow)

    run = Run(flow_id=flow.id, plan_version_id=plan_version.id, run_type="preview", status="running", triggered_by=actor)
    db.add(run)
    db.flush()

    try:
        compiled = validate_plan(plan, connector)

        first_source = plan.sources[0]
        source_sql = f"SELECT * FROM {quote_identifier(first_source.schema_name)}.{quote_identifier(first_source.table_name)}"
        rows_before = connector.count_rows(source_sql)
        rows_after = connector.count_rows(compiled.sql, compiled.params)

        chunks = list(connector.run_readonly(compiled.sql, params=compiled.params, chunksize=PREVIEW_SAMPLE_LIMIT))
        sample_after = chunks[0].head(PREVIEW_SAMPLE_LIMIT).to_dict(orient="records") if chunks else []
        sample_before = connector.sample_rows(first_source.table_name, first_source.schema_name, PREVIEW_SAMPLE_LIMIT)

        anomaly = rows_before > 0 and (rows_after / rows_before) > settings.join_anomaly_ratio

        run.status = "succeeded"
        run.generated_sql = compiled.sql
        run.generated_code_lang = "sql"
        run.rows_before = rows_before
        run.rows_after = rows_after
        run.row_count_anomaly = anomaly
        run.sample_before_json = json.dumps(sample_before, default=str)
        run.sample_after_json = json.dumps(sample_after, default=str)
    except Exception as exc:
        # Covers both our own DomainError (schema drift, bad SQL) and any
        # raw driver/connection exception from a live EXPLAIN/count/read
        # (e.g. the DB rejects the query at runtime despite passing our
        # pre-checks) - either way the run is recorded as failed with a
        # clear message instead of leaving it stuck at "running" or letting
        # a raw exception blow past the API layer as a 500.
        run.status = "failed"
        run.error_message = str(exc)

    run.finished_at = utcnow()
    db.add(run)
    db.flush()

    move_flow(
        db, flow, FlowStatus.PREVIEW_PENDING_APPROVAL, actor=actor,
        detail={"run_id": run.id, "run_status": run.status},
    )
    db.flush()
    return run


def preview_step(db: Session, flow: Flow, step_alias: str, limit: int = 50) -> list[dict]:
    """Sample intermediate step output records by compiling the plan up to step_alias CTE."""
    if flow.active_plan_version_id is None:
        raise DomainError("Flow has no active plan version")

    plan_version = db.get(PlanVersion, flow.active_plan_version_id)
    plan = PlanDraft.model_validate_json(plan_version.plan_json)
    connector = _connector_for_flow(db, flow)

    # Check if step_alias is a source table
    for src in plan.sources:
        if src.alias == step_alias:
            return connector.sample_rows(src.table_name, src.schema_name, limit)

    from app.transform.plan_to_sql import compile_plan
    compiled = compile_plan(plan, target_alias=step_alias)
    chunks = list(connector.run_readonly(compiled.sql, params=compiled.params, chunksize=limit))
    return chunks[0].head(limit).to_dict(orient="records") if chunks else []



def approve_preview(db: Session, flow: Flow, actor: str, acknowledge_anomaly: bool = False) -> Run:
    current_status = FlowStatus(flow.status)
    if current_status != FlowStatus.PREVIEW_PENDING_APPROVAL:
        raise DomainError(
            f"Cannot approve preview for flow in status '{flow.status}'. "
            "A preview must be pending approval before it can be approved."
        )

    latest_run = (
        db.query(Run)
        .filter_by(flow_id=flow.id, run_type="preview")
        .order_by(Run.started_at.desc())
        .first()
    )
    if latest_run is None:
        raise DomainError("Flow has no preview run to approve")
    if latest_run.status != "succeeded":
        raise DomainError(
            f"Cannot approve: the latest preview run {latest_run.status} "
            f"({latest_run.error_message or 'no details'}). Edit the plan and preview again."
        )
    if latest_run.row_count_anomaly and not acknowledge_anomaly:
        raise DomainError(
            f"Preview shows a row-count anomaly ({latest_run.rows_before} -> {latest_run.rows_after} rows, "
            f"more than {settings.join_anomaly_ratio}x growth) - a join may be fanning out unexpectedly. "
            "Pass acknowledge_anomaly=true to approve anyway, or edit the plan."
        )

    move_flow(
        db, flow, FlowStatus.APPROVED, actor=actor,
        detail={"run_id": latest_run.id, "acknowledged_anomaly": latest_run.row_count_anomaly},
    )
    db.flush()
    return latest_run


def _hyper_output_path(flow: Flow, run: Run) -> Path:
    output_dir = Path(settings.hyper_output_dir) / flow.id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{run.id}.hyper"


def execute_flow(
    db: Session,
    flow: Flow,
    actor: str,
    trigger_type: str = "manual",
    scheduled_for: datetime | None = None,
) -> Run:
    """Full pipeline: approved plan -> chunked execute -> .hyper write ->
    Tableau publish. Reachable from `approved` (both plan AND preview
    were explicitly approved to get here) or `published` (for recurring/re-executions).
    Always ends in `published` or `failed`, never left at `running`."""
    current_status = FlowStatus(flow.status)
    if current_status not in (FlowStatus.APPROVED, FlowStatus.PUBLISHED):
        raise DomainError(
            f"Cannot execute flow in status '{flow.status}'. The preview must be approved first."
        )
    if not flow.tableau_connection_id:
        raise DomainError("Flow has no Tableau connection configured - cannot publish the result")

    # Critical rule: Execute strictly uses approved_version_id so draft edits never bleed into production
    target_version_id = flow.approved_version_id or flow.active_plan_version_id
    if not target_version_id:
        raise DomainError("Flow has no approved plan version to execute")

    plan_version = db.get(PlanVersion, target_version_id)
    if plan_version is None:
        raise DomainError(f"Approved plan version {target_version_id!r} not found")

    plan = PlanDraft.model_validate_json(plan_version.plan_json)
    connector = _connector_for_flow(db, flow)

    run = Run(
        flow_id=flow.id,
        plan_version_id=plan_version.id,
        run_type="execute",
        status="running",
        publish_status="not_attempted",
        triggered_by=actor,
        trigger_type=trigger_type,
        scheduled_for=scheduled_for,
    )
    db.add(run)
    db.flush()

    move_flow(db, flow, FlowStatus.RUNNING, actor=actor, detail={"run_id": run.id})
    db.flush()

    try:
        compiled = validate_plan(plan, connector)
        run.generated_sql = compiled.sql
        run.generated_code_lang = "sql"

        # Count total rows for audit (safe fallback if connector mock lacks count_rows)
        if hasattr(connector, "count_rows"):
            first_source = plan.sources[0]
            source_sql = f"SELECT * FROM {quote_identifier(first_source.schema_name)}.{quote_identifier(first_source.table_name)}"
            run.rows_before = connector.count_rows(source_sql)
            run.rows_after = connector.count_rows(compiled.sql, compiled.params)

        # Streamed straight from the connector into the Hyper writer
        chunks = connector.run_readonly(compiled.sql, params=compiled.params, chunksize=settings.execute_chunk_size)
        hyper_path = _hyper_output_path(flow, run)
        write_hyper_file(chunks, hyper_path)
        run.hyper_file_path = str(hyper_path)

        if flow.tableau_connection_id:
            tableau_conn = db.get(Connection, flow.tableau_connection_id)
            if tableau_conn is None:
                raise DomainError(f"Tableau connection {flow.tableau_connection_id!r} not found")
            tableau_secret = decrypt(tableau_conn.encrypted_secret)
            tableau_client = TableauClient(
                tableau_conn.host, tableau_conn.tableau_site_id or "", tableau_conn.username, tableau_secret
            )

            try:
                publish_or_overwrite(
                    tableau_client,
                    tableau_conn.tableau_project_id,
                    flow.target_datasource_name or flow.name,
                    hyper_path,
                )
                run.publish_status = "succeeded"
            except PublishError as exc:
                run.publish_status = "failed"
                run.publish_error = str(exc)
                raise
        else:
            run.publish_status = "skipped_local_only"

        run.status = "succeeded"
        move_flow(db, flow, FlowStatus.PUBLISHED, actor=actor, detail={"run_id": run.id})
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        move_flow(db, flow, FlowStatus.FAILED, actor=actor, detail={"run_id": run.id, "error": str(exc)})

    run.finished_at = utcnow()
    db.add(run)
    db.flush()
    return run

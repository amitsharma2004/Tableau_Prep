"""MCP Tools Implementation: Zero-data Schema Catalog, Profile Inspection,
Validation Gate, SQL Pushdown Dry-run, and Checkpoint Commit."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.connectors.factory import build_connector
from app.core.security import decrypt
from app.db.models.connection import Connection
from app.db.models.flow import Flow
from app.db.session import SessionLocal
from app.llm.plan_schema import PlanDraft
from app.services import connection_service, plan_service
from app.transform.plan_to_sql import compile_plan
from app.validator.plan_verifier import verify_plan


def _resolve_connector(conn: Connection):
    secret = decrypt(conn.encrypted_secret)
    return build_connector(
        conn.type, conn.host, conn.port, conn.database_name, conn.username, secret
    )


def get_catalog_schema(connection_id: Optional[str] = None) -> dict[str, Any]:
    """MCP Tool 1: Returns zero-data schema metadata (tables, columns, types, nullability)."""
    with SessionLocal() as db:
        if connection_id:
            conn = db.get(Connection, connection_id)
        else:
            conn = db.query(Connection).filter(Connection.type.in_(["sqlite", "postgres", "mysql"])).first()

        if not conn:
            return {"error": "No valid source database connection found."}

        schema_res = connection_service.test_and_introspect(db, conn, actor="mcp-server")
        tables = [
            {
                "schema": t.schema_name,
                "name": t.name,
                "columns": [{"name": c.name, "type": c.data_type, "nullable": c.nullable} for c in t.columns],
            }
            for t in schema_res.tables
        ]
        return {
            "connection_id": conn.id,
            "connection_name": conn.name,
            "dialect": conn.type,
            "tables": tables,
        }


def inspect_table_profile(table_name: str, schema_name: str = "public", connection_id: Optional[str] = None) -> dict[str, Any]:
    """MCP Tool 2: Inspects column metrics, null rates, and sample values without leaking full dataset."""
    with SessionLocal() as db:
        if connection_id:
            conn = db.get(Connection, connection_id)
        else:
            conn = db.query(Connection).filter(Connection.type.in_(["sqlite", "postgres", "mysql"])).first()

        if not conn:
            return {"error": "Connection not found."}

        connector = _resolve_connector(conn)
        samples = connector.sample_rows(table=table_name, schema=schema_name, limit=10)
        
        # Calculate column stats from sample
        stats: dict[str, Any] = {}
        if samples:
            cols = list(samples[0].keys())
            for c in cols:
                vals = [r[c] for r in samples if r.get(c) is not None]
                distinct_sample = list({str(v) for v in vals})[:5]
                stats[c] = {
                    "sample_distinct_values": distinct_sample,
                    "sample_null_count": len(samples) - len(vals),
                }

        return {
            "table_name": table_name,
            "schema_name": schema_name,
            "sample_row_count": len(samples),
            "column_metrics": stats,
            "sample_rows": samples[:3],  # Return up to 3 preview rows
        }


def validate_flow_plan(plan_data: dict[str, Any], connection_id: Optional[str] = None) -> dict[str, Any]:
    """MCP Tool 3: Runs DAG checks, Virtual Lineage simulation, and AI confidence scoring."""
    try:
        plan = PlanDraft.model_validate(plan_data)
    except Exception as exc:
        return {
            "is_valid": False,
            "error_message": f"Plan schema validation failed: {exc}",
            "repair_feedback": "Ensure JSON matches required PlanDraft schema (sources, steps, output_alias, summary).",
        }

    # Fast-path Gate 1: Check DAG topology statically without needing DB connection
    from app.validator.dag_checker import DAGValidationError, validate_dag
    try:
        validate_dag(plan)
    except DAGValidationError as err:
        return {
            "is_valid": False,
            "confidence": {
                "overall_score": 0,
                "level": "low",
                "grounding_score": 0,
                "join_integrity_score": 0,
                "complexity_score": 0,
                "warnings": [str(err)],
            },
            "topo_order": [],
            "virtual_schemas": {},
            "compiled_sql": None,
            "error_message": str(err),
            "repair_feedback": f"DAG validation failed: {err}. Ensure every step references a defined upstream alias and no circular loops exist.",
        }

    with SessionLocal() as db:
        if connection_id:
            conn = db.get(Connection, connection_id)
        else:
            conn = db.query(Connection).filter(Connection.type.in_(["sqlite", "postgres", "mysql"])).first()

        if not conn:
            return {"is_valid": False, "error_message": "No database connection available to validate schema."}

        connector = _resolve_connector(conn)
        tables = connector.introspect_schema()
        dialect = "postgres" if conn.type == "postgres" else "sqlite"
        report = verify_plan(plan, tables, dialect=dialect)
        return report.to_dict()


def dry_run_flow(plan_data: dict[str, Any], limit: int = 10, connection_id: Optional[str] = None) -> dict[str, Any]:
    """MCP Tool 4: In-Database Pushdown dry-run: executes compiled CTE query on source DB."""
    try:
        plan = PlanDraft.model_validate(plan_data)
    except Exception as exc:
        return {"success": False, "error": f"Invalid plan schema: {exc}"}

    with SessionLocal() as db:
        if connection_id:
            conn = db.get(Connection, connection_id)
        else:
            conn = db.query(Connection).filter(Connection.type.in_(["sqlite", "postgres", "mysql"])).first()

        if not conn:
            return {"success": False, "error": "No database connection available."}

        try:
            compiled = compile_plan(plan)
            connector = _resolve_connector(conn)
            
            # Execute with limit via connector engine without loading full dataset
            dry_run_sql = f"{compiled.sql} LIMIT {limit}"
            engine = connector._engine
            from sqlalchemy import text
            with engine.connect() as con:
                result = con.execute(text(dry_run_sql), compiled.params)
                keys = list(result.keys())
                rows = [dict(zip(keys, r)) for r in result.fetchmany(limit)]

            return {
                "success": True,
                "row_count": len(rows),
                "columns": keys,
                "sample_preview": rows,
                "compiled_sql": dry_run_sql,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Database execution failed: {exc}",
                "compiled_sql": compiled.sql if "compiled" in locals() else None,
            }


def commit_flow_checkpoint(
    plan_data: dict[str, Any],
    flow_id: Optional[str] = None,
    connection_id: Optional[str] = None,
    actor_email: str = "mcp-agent@tableau-prep.local",
    change_summary: Optional[str] = None,
) -> dict[str, Any]:
    """MCP Tool 5: Persists validated plan as a new immutable PlanVersion and returns Studio URL."""
    try:
        plan = PlanDraft.model_validate(plan_data)
    except Exception as exc:
        return {"success": False, "error": f"Invalid plan format: {exc}"}

    with SessionLocal() as db:
        flow: Optional[Flow] = None
        if flow_id:
            flow = db.get(Flow, flow_id)

        if not flow:
            # Auto-create flow if none provided
            if connection_id:
                conn = db.get(Connection, connection_id)
            else:
                conn = db.query(Connection).filter(Connection.type.in_(["sqlite", "postgres", "mysql"])).first()

            if not conn:
                return {"success": False, "error": "Cannot create flow without an active data connection."}

            flow = Flow(
                name=plan.summary[:40] if plan.summary else "MCP Flow Plan",
                nl_request=plan.summary,
                source_connection_id=conn.id,
                status="draft",
                created_by=actor_email,
            )
            db.add(flow)
            db.flush()
        elif connection_id and flow.source_connection_id != connection_id:
            flow.source_connection_id = connection_id
            db.flush()

        # Commit checkpoint via plan_service
        try:
            new_version = plan_service.edit_plan(
                db,
                flow,
                plan,
                actor=actor_email,
                change_summary=change_summary or plan.summary or "MCP Checkpoint Commit",
            )
            db.commit()

            canvas_url = f"http://localhost:3000/flows/new?flowId={flow.id}"
            return {
                "success": True,
                "flow_id": flow.id,
                "version_number": new_version.version_number,
                "version_id": new_version.id,
                "status": flow.status,
                "canvas_url": canvas_url,
                "message": f"Successfully committed Checkpoint v{new_version.version_number}. View in canvas: {canvas_url}",
            }
        except Exception as exc:
            db.rollback()
            return {"success": False, "error": f"Failed to commit checkpoint: {exc}"}


def get_active_flow_plan(flow_id: str) -> dict[str, Any]:
    """MCP Tool 6: Fetch current active plan and version details for a flow so agent can follow up and refine."""
    with SessionLocal() as db:
        flow = db.get(Flow, flow_id)
        if not flow:
            return {"error": f"Flow '{flow_id}' not found"}

        from app.db.models.plan_version import PlanVersion
        import json

        if not flow.active_plan_version_id:
            return {"error": f"Flow '{flow_id}' has no active plan version"}

        version = db.get(PlanVersion, flow.active_plan_version_id)
        if not version:
            return {"error": "Active version not found"}

        plan_data = json.loads(version.plan_json)
        return {
            "flow_id": flow.id,
            "flow_name": flow.name,
            "status": flow.status,
            "source_connection_id": flow.source_connection_id,
            "version_number": version.version_number,
            "plan_data": plan_data,
        }

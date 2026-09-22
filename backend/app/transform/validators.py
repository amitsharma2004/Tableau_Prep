"""Validates a plan/compiled SQL before it is ever run against a real
database. Enforces two build-plan edge cases:
- "wrong/invalid SQL from the LLM" -> validate_select_only()
- "schema drift" -> check_schema_drift()
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.connectors.base import TableInfo
from app.core.errors import SchemaDriftError, SQLValidationError
from app.llm.plan_schema import PlanDraft

_FORBIDDEN_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
)


def validate_select_only(sql: str, dialect: str = "postgres") -> None:
    """Defense in depth alongside the DB-level read-only user check
    (connection_service.py): even if plan_to_sql.py had a bug, this rejects
    anything that isn't a single read-only SELECT/CTE before it reaches the
    database."""
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except sqlglot.errors.ParseError as exc:
        raise SQLValidationError(f"Generated SQL failed to parse: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLValidationError("Generated SQL must be exactly one statement")

    stmt = statements[0]
    if not isinstance(stmt, (exp.Select, exp.With)):
        raise SQLValidationError(f"Generated SQL must be a read-only SELECT, got: {type(stmt).__name__}")

    for _ in stmt.find_all(*_FORBIDDEN_NODE_TYPES):
        raise SQLValidationError("Generated SQL contains a forbidden write/DDL statement")


def check_schema_drift(plan: PlanDraft, live_tables: list[TableInfo]) -> None:
    """Re-introspected `live_tables` vs. what the plan assumes. Only checks
    source tables/columns the plan references directly - columns produced by
    an intermediate step (e.g. a join's combined output) would need full
    type inference to check and are out of scope for this MVP validator."""
    live_columns: dict[tuple[str, str], set[str]] = {
        (t.schema, t.name): {c.name for c in t.columns} for t in live_tables
    }

    for src in plan.sources:
        key = (src.schema_name, src.table_name)
        if key not in live_columns:
            raise SchemaDriftError(f"{src.schema_name}.{src.table_name}")

    alias_to_table = {src.alias: (src.schema_name, src.table_name) for src in plan.sources}

    def _check_column(alias: str, column: str) -> None:
        table_key = alias_to_table.get(alias)
        if table_key is None:
            return  # alias is a prior step's output, not a live table - nothing to check
        if column not in live_columns.get(table_key, set()):
            raise SchemaDriftError(f"{table_key[0]}.{table_key[1]}", column)

    for step in plan.steps:
        if step.type == "filter":
            for cond in step.conditions:
                _check_column(step.target, cond.column)
        elif step.type == "drop_nulls":
            for col in step.columns:
                _check_column(step.target, col)
        elif step.type == "join":
            for pair in step.on:
                lcol, rcol = pair
                _check_column(step.left, lcol)
                _check_column(step.right, rcol)
        elif step.type == "rename":
            for old in step.mapping:
                _check_column(step.target, old)
        elif step.type == "select_columns":
            for col in step.columns:
                _check_column(step.target, col)
        elif step.type == "aggregate":
            for col in step.group_by:
                _check_column(step.target, col)
            for agg in step.aggregations:
                _check_column(step.target, agg.column)
        elif step.type == "dedupe" and step.columns:
            for col in step.columns:
                _check_column(step.target, col)

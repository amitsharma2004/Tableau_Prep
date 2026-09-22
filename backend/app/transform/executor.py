"""Orchestrates: compile plan -> validate (schema drift + SELECT-only) ->
EXPLAIN dry-run -> chunked execute. Never blind-executes plan-derived SQL -
this is the single choke point every run (preview or full execute) must
pass through before touching real data."""
from __future__ import annotations

from typing import Iterator

import pandas as pd

from app.connectors.base import DBConnector
from app.llm.plan_schema import PlanDraft
from app.transform.plan_to_sql import CompiledSQL, compile_plan
from app.transform.validators import check_schema_drift, validate_select_only


def validate_plan(plan: PlanDraft, connector: DBConnector, dialect: str = "postgres") -> CompiledSQL:
    """Compile + validate a plan without executing it against real data.
    Raises SchemaDriftError / SQLValidationError / ConnectionFailedError-ish
    exceptions from the connector's EXPLAIN if anything is wrong."""
    live_tables = connector.introspect_schema()
    check_schema_drift(plan, live_tables)

    compiled = compile_plan(plan)
    validate_select_only(compiled.sql, dialect=dialect)
    connector.explain(compiled.sql, params=compiled.params)
    return compiled


def execute_plan(
    plan: PlanDraft,
    connector: DBConnector,
    chunksize: int = 50_000,
    dialect: str = "postgres",
) -> Iterator[pd.DataFrame]:
    """Validate then stream the plan's result in chunks - never materializes
    the full result set at once (see build plan 'large tables')."""
    compiled = validate_plan(plan, connector, dialect=dialect)
    yield from connector.run_readonly(compiled.sql, params=compiled.params, chunksize=chunksize)

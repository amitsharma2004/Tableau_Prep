import pandas as pd
import pytest

from app.core.errors import SchemaDriftError, SQLValidationError
from app.llm.plan_schema import PlanDraft
from app.transform import executor
from tests.test_plan_schema import VALID_PLAN
from tests.test_validators import LIVE_TABLES


class FakeConnector:
    """Records call order so tests can prove executor.py always validates
    and dry-runs (EXPLAIN) before ever touching real data via run_readonly."""

    def __init__(self, live_tables=LIVE_TABLES, explain_should_fail=False):
        self.live_tables = live_tables
        self.explain_should_fail = explain_should_fail
        self.calls: list[str] = []

    def introspect_schema(self):
        self.calls.append("introspect_schema")
        return self.live_tables

    def explain(self, sql, params=None):
        self.calls.append("explain")
        if self.explain_should_fail:
            raise RuntimeError("simulated: database rejected this query")

    def run_readonly(self, sql, params=None, chunksize=50_000):
        self.calls.append("run_readonly")
        yield pd.DataFrame([{"region": "North", "total_revenue": 250.0}])


def test_validate_plan_runs_schema_check_then_explain_in_order():
    plan = PlanDraft.model_validate(VALID_PLAN)
    connector = FakeConnector()

    compiled = executor.validate_plan(plan, connector)

    assert connector.calls == ["introspect_schema", "explain"]
    assert compiled.sql.startswith("WITH ")


def test_validate_plan_raises_schema_drift_before_ever_calling_explain():
    plan_dict = dict(VALID_PLAN)
    plan_dict["sources"] = [
        {"alias": "orders", "schema_name": "public", "table_name": "orders_typo"},
        *VALID_PLAN["sources"][1:],
    ]
    plan = PlanDraft.model_validate(plan_dict)
    connector = FakeConnector()

    with pytest.raises(SchemaDriftError):
        executor.validate_plan(plan, connector)

    assert "explain" not in connector.calls  # never dry-runs a plan with known-bad schema


def test_execute_plan_never_runs_readonly_when_explain_rejects_the_query():
    plan = PlanDraft.model_validate(VALID_PLAN)
    connector = FakeConnector(explain_should_fail=True)

    with pytest.raises(RuntimeError):
        list(executor.execute_plan(plan, connector))

    assert connector.calls == ["introspect_schema", "explain"]
    assert "run_readonly" not in connector.calls


def test_execute_plan_streams_chunks_only_after_successful_validation():
    plan = PlanDraft.model_validate(VALID_PLAN)
    connector = FakeConnector()

    chunks = list(executor.execute_plan(plan, connector))

    assert connector.calls == ["introspect_schema", "explain", "run_readonly"]
    assert len(chunks) == 1
    assert chunks[0].iloc[0]["region"] == "North"

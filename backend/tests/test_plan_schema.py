import pytest
from pydantic import ValidationError

from app.llm.plan_schema import PlanDraft


VALID_PLAN = {
    "summary": "Join orders to customers, drop rows with a null email, and total revenue per region.",
    "sources": [
        {"alias": "orders", "schema_name": "public", "table_name": "orders"},
        {"alias": "customers", "schema_name": "public", "table_name": "customers"},
    ],
    "steps": [
        {
            "type": "join",
            "left": "orders",
            "right": "customers",
            "join_type": "inner",
            "on": [["customer_id", "id"]],
            "output_alias": "joined",
        },
        {
            "type": "drop_nulls",
            "target": "joined",
            "output_alias": "cleaned",
            "columns": ["email"],
        },
        {
            "type": "aggregate",
            "target": "cleaned",
            "output_alias": "result",
            "group_by": ["region"],
            "aggregations": [{"column": "amount", "function": "sum", "alias": "total_revenue"}],
        },
    ],
    "output_alias": "result",
}


def test_valid_plan_parses():
    plan = PlanDraft.model_validate(VALID_PLAN)
    assert plan.output_alias == "result"
    assert len(plan.steps) == 3
    assert plan.steps[0].type == "join"
    assert plan.steps[2].aggregations[0].function == "sum"


def test_plan_round_trips_through_json():
    plan = PlanDraft.model_validate(VALID_PLAN)
    restored = PlanDraft.model_validate_json(plan.model_dump_json())
    assert restored == plan


def test_unknown_step_type_is_rejected():
    bad_plan = dict(VALID_PLAN)
    bad_plan["steps"] = [{"type": "drop_table", "target": "orders", "output_alias": "x"}]
    with pytest.raises(ValidationError):
        PlanDraft.model_validate(bad_plan)


def test_missing_required_field_is_rejected():
    bad_plan = dict(VALID_PLAN)
    bad_plan["steps"] = [{"type": "join", "left": "orders", "right": "customers"}]  # missing join_type/on/output_alias
    with pytest.raises(ValidationError):
        PlanDraft.model_validate(bad_plan)

import pytest

from app.core.errors import SQLValidationError
from app.llm.plan_schema import PlanDraft
from app.transform.plan_to_sql import compile_plan
from tests.test_plan_schema import VALID_PLAN


def test_compile_plan_produces_a_single_with_select_statement():
    plan = PlanDraft.model_validate(VALID_PLAN)
    compiled = compile_plan(plan)

    assert compiled.sql.startswith("WITH ")
    assert '"joined" AS (' in compiled.sql
    assert '"cleaned" AS (' in compiled.sql
    assert '"result" AS (' in compiled.sql
    assert compiled.sql.rstrip().endswith('SELECT * FROM "result"')


def test_compile_plan_uses_bound_params_for_filter_values_not_inline_literals():
    plan_dict = dict(VALID_PLAN)
    plan_dict["steps"] = [
        {
            "type": "filter",
            "target": "orders",
            "output_alias": "result",
            "conditions": [{"column": "region", "operator": "=", "value": "North"}],
        }
    ]
    plan_dict["output_alias"] = "result"
    plan = PlanDraft.model_validate(plan_dict)

    compiled = compile_plan(plan)

    assert "North" not in compiled.sql  # value must never be inlined
    assert ":p0" in compiled.sql
    assert compiled.params == {"p0": "North"}


def test_compile_plan_rejects_reference_to_unknown_alias():
    plan_dict = dict(VALID_PLAN)
    plan_dict["steps"] = [
        {
            "type": "filter",
            "target": "does_not_exist",
            "output_alias": "result",
            "conditions": [{"column": "x", "operator": "is_null"}],
        }
    ]
    plan_dict["output_alias"] = "result"
    plan = PlanDraft.model_validate(plan_dict)

    with pytest.raises(SQLValidationError):
        compile_plan(plan)


def test_compile_plan_rejects_output_alias_not_produced_by_any_step():
    plan_dict = dict(VALID_PLAN)
    plan_dict["output_alias"] = "never_defined"
    plan = PlanDraft.model_validate(plan_dict)

    with pytest.raises(SQLValidationError):
        compile_plan(plan)


def test_compile_plan_rejects_duplicate_source_alias():
    plan_dict = dict(VALID_PLAN)
    plan_dict["sources"] = [
        {"alias": "orders", "schema_name": "public", "table_name": "orders"},
        {"alias": "orders", "schema_name": "public", "table_name": "orders_backup"},
    ]
    with pytest.raises(SQLValidationError):
        compile_plan(PlanDraft.model_validate(plan_dict))


def test_compile_plan_join_uses_parameter_free_identifier_only_on_clause():
    plan = PlanDraft.model_validate(VALID_PLAN)
    compiled = compile_plan(plan)

    assert 'ON "orders"."customer_id" = "customers"."id"' in compiled.sql
    assert "INNER JOIN" in compiled.sql


def test_compile_plan_in_operator_binds_each_value_as_its_own_param():
    plan_dict = dict(VALID_PLAN)
    plan_dict["steps"] = [
        {
            "type": "filter",
            "target": "orders",
            "output_alias": "result",
            "conditions": [{"column": "region", "operator": "in", "value": ["North", "South"]}],
        }
    ]
    plan_dict["output_alias"] = "result"
    plan = PlanDraft.model_validate(plan_dict)

    compiled = compile_plan(plan)

    assert set(compiled.params.values()) == {"North", "South"}
    assert "IN (:p0, :p1)" in compiled.sql


def test_compile_union_step():
    plan_dict = {
        "summary": "Union two tables",
        "sources": [
            {"alias": "q1_sales", "schema_name": "public", "table_name": "sales_q1"},
            {"alias": "q2_sales", "schema_name": "public", "table_name": "sales_q2"},
        ],
        "steps": [
            {
                "type": "union",
                "inputs": ["q1_sales", "q2_sales"],
                "output_alias": "all_sales",
                "distinct": False,
            }
        ],
        "output_alias": "all_sales",
    }
    plan = PlanDraft.model_validate(plan_dict)
    compiled = compile_plan(plan)
    assert "UNION ALL" in compiled.sql
    assert '"all_sales" AS (SELECT * FROM "public"."sales_q1" AS "q1_sales" UNION ALL SELECT * FROM "public"."sales_q2" AS "q2_sales")' in compiled.sql


"""Tests for the DAG topology checker, lineage simulator, confidence scorer, and master plan verifier."""
import pytest

from app.connectors.base import ColumnInfo, TableInfo
from app.llm.plan_schema import (
    AggregateStep,
    AggregationSpec,
    CastStep,
    DedupeStep,
    DropNullsStep,
    FilterCondition,
    FilterStep,
    JoinStep,
    PlanDraft,
    RenameStep,
    SelectColumnsStep,
    SourceTableRef,
    TextCleanStep,
)
from app.validator.dag_checker import DAGValidationError, validate_dag
from app.validator.lineage_simulator import LineageValidationError, simulate_lineage
from app.validator.confidence_scorer import score_plan_confidence
from app.validator.plan_verifier import verify_plan


@pytest.fixture
def sample_catalog_tables():
    return [
        TableInfo(
            name="orders",
            schema="public",
            columns=[
                ColumnInfo(name="id", data_type="integer", nullable=False),
                ColumnInfo(name="customer_id", data_type="integer", nullable=False),
                ColumnInfo(name="amount", data_type="numeric", nullable=True),
                ColumnInfo(name="status", data_type="varchar", nullable=False),
                ColumnInfo(name="order_date", data_type="date", nullable=False),
            ],
        ),
        TableInfo(
            name="customers",
            schema="public",
            columns=[
                ColumnInfo(name="id", data_type="integer", nullable=False),
                ColumnInfo(name="name", data_type="varchar", nullable=False),
                ColumnInfo(name="region", data_type="varchar", nullable=True),
                ColumnInfo(name="email", data_type="varchar", nullable=True),
            ],
        ),
    ]


def test_valid_linear_dag_passes():
    plan = PlanDraft(
        summary="Simple filter and select",
        sources=[SourceTableRef(alias="orders", schema_name="public", table_name="orders")],
        steps=[
            FilterStep(
                target="orders",
                output_alias="filtered",
                conditions=[FilterCondition(column="status", operator="=", value="Completed")],
            ),
            SelectColumnsStep(target="filtered", output_alias="selected", columns=["id", "amount"]),
        ],
        output_alias="selected",
    )
    order = validate_dag(plan)
    assert order == ["orders", "filtered", "selected"]


def test_cyclic_dag_fails():
    plan = PlanDraft(
        summary="Cyclic plan",
        sources=[SourceTableRef(alias="orders", schema_name="public", table_name="orders")],
        steps=[
            FilterStep(
                target="b_step",
                output_alias="a_step",
                conditions=[FilterCondition(column="status", operator="=", value="Completed")],
            ),
            SelectColumnsStep(target="a_step", output_alias="b_step", columns=["id"]),
        ],
        output_alias="b_step",
    )
    with pytest.raises(DAGValidationError) as exc:
        validate_dag(plan)
    assert "Cyclic dependency detected" in str(exc.value)


def test_unreachable_output_alias_fails():
    plan = PlanDraft(
        summary="Unreachable output",
        sources=[SourceTableRef(alias="orders", schema_name="public", table_name="orders")],
        steps=[
            FilterStep(
                target="orders",
                output_alias="filtered",
                conditions=[FilterCondition(column="status", operator="=", value="Completed")],
            ),
        ],
        output_alias="non_existent_output",
    )
    with pytest.raises(DAGValidationError) as exc:
        validate_dag(plan)
    assert "output_alias 'non_existent_output' is not defined" in str(exc.value)


def test_lineage_simulator_tracks_renames_and_joins(sample_catalog_tables):
    plan = PlanDraft(
        summary="Rename then join",
        sources=[
            SourceTableRef(alias="orders", schema_name="public", table_name="orders"),
            SourceTableRef(alias="customers", schema_name="public", table_name="customers"),
        ],
        steps=[
            RenameStep(
                target="orders",
                output_alias="orders_renamed",
                mapping={"amount": "total_revenue"},
            ),
            JoinStep(
                left="orders_renamed",
                right="customers",
                join_type="inner",
                on=[["customer_id", "id"]],
                output_alias="joined",
            ),
        ],
        output_alias="joined",
    )
    schemas = simulate_lineage(plan, sample_catalog_tables)
    assert "joined" in schemas
    joined_cols = schemas["joined"].column_names()
    assert "total_revenue" in joined_cols
    assert "name" in joined_cols
    assert "region" in joined_cols


def test_lineage_simulator_catches_missing_column_with_suggestion(sample_catalog_tables):
    plan = PlanDraft(
        summary="Filter on hallucinated column",
        sources=[SourceTableRef(alias="orders", schema_name="public", table_name="orders")],
        steps=[
            FilterStep(
                target="orders",
                output_alias="filtered",
                conditions=[FilterCondition(column="amont", operator=">", value=100)],  # typo in amount
            ),
        ],
        output_alias="filtered",
    )
    with pytest.raises(LineageValidationError) as exc:
        simulate_lineage(plan, sample_catalog_tables)
    assert "Filter column 'amont' does not exist" in str(exc.value)
    assert "amount" in exc.value.suggestions


def test_lineage_catches_access_to_pruned_column_after_aggregate(sample_catalog_tables):
    plan = PlanDraft(
        summary="Aggregate drops columns, next step tries to access it",
        sources=[SourceTableRef(alias="orders", schema_name="public", table_name="orders")],
        steps=[
            AggregateStep(
                target="orders",
                output_alias="agg",
                group_by=["status"],
                aggregations=[AggregationSpec(column="amount", function="sum", alias="total_amount")],
            ),
            FilterStep(
                target="agg",
                output_alias="filtered",
                conditions=[FilterCondition(column="order_date", operator=">", value="2026-01-01")],  # pruned!
            ),
        ],
        output_alias="filtered",
    )
    with pytest.raises(LineageValidationError) as exc:
        simulate_lineage(plan, sample_catalog_tables)
    assert "Filter column 'order_date' does not exist in 'agg'" in str(exc.value)


def test_confidence_scorer_assigns_high_score_to_clean_plan(sample_catalog_tables):
    plan = PlanDraft(
        summary="Clean join on keys",
        sources=[
            SourceTableRef(alias="orders", schema_name="public", table_name="orders"),
            SourceTableRef(alias="customers", schema_name="public", table_name="customers"),
        ],
        steps=[
            JoinStep(
                left="orders",
                right="customers",
                join_type="inner",
                on=[["customer_id", "id"]],
                output_alias="joined",
            ),
        ],
        output_alias="joined",
    )
    report = score_plan_confidence(plan, sample_catalog_tables)
    assert report.overall_score >= 85
    assert report.level == "high"
    assert report.join_integrity_score == 100


def test_master_verify_plan_end_to_end(sample_catalog_tables):
    plan = PlanDraft(
        summary="End to end test",
        sources=[
            SourceTableRef(alias="orders", schema_name="public", table_name="orders"),
            SourceTableRef(alias="customers", schema_name="public", table_name="customers"),
        ],
        steps=[
            FilterStep(
                target="orders",
                output_alias="orders_filtered",
                conditions=[FilterCondition(column="status", operator="=", value="Completed")],
            ),
            JoinStep(
                left="orders_filtered",
                right="customers",
                join_type="inner",
                on=[["customer_id", "id"]],
                output_alias="joined",
            ),
        ],
        output_alias="joined",
    )
    report = verify_plan(plan, sample_catalog_tables, dialect="postgres")
    assert report.is_valid is True
    assert report.compiled_sql is not None
    assert "WITH" in report.compiled_sql
    assert report.confidence.overall_score >= 85


# ==============================================================================
# CRITICAL & "TEDE" (EDGE-CASE) HARDCORE STRESS TESTS
# ==============================================================================

def test_critical_multi_node_indirect_cycle():
    """Tede Case 1: Indirect cycle A -> B -> C -> A caught by Kahn's algorithm."""
    plan = PlanDraft(
        summary="Indirect cycle test",
        sources=[SourceTableRef(alias="orders", schema_name="public", table_name="orders")],
        steps=[
            FilterStep(
                target="orders",
                output_alias="step_a",
                conditions=[FilterCondition(column="status", operator="=", value="Completed")],
            ),
            RenameStep(
                target="step_c",  # Forward reference / cyclic dependency
                output_alias="step_b",
                mapping={"amount": "amt"},
            ),
            DedupeStep(
                target="step_b",
                output_alias="step_c",
            ),
        ],
        output_alias="step_c",
    )
    with pytest.raises(DAGValidationError) as exc:
        validate_dag(plan)
    assert "references input 'step_c' which is never defined" in str(exc.value) or "Cyclic" in str(exc.value)


def test_critical_colliding_join_column_lineage(sample_catalog_tables):
    """Tede Case 2: Both orders and customers have 'id'. Lineage must disambiguate right id as customers_id."""
    plan = PlanDraft(
        summary="Join colliding columns",
        sources=[
            SourceTableRef(alias="orders", schema_name="public", table_name="orders"),
            SourceTableRef(alias="customers", schema_name="public", table_name="customers"),
        ],
        steps=[
            JoinStep(
                left="orders",
                right="customers",
                join_type="inner",
                on=[["customer_id", "id"]],
                output_alias="joined",
            ),
            # Downstream filter referencing disambiguated customers_id
            FilterStep(
                target="joined",
                output_alias="filtered_cust",
                conditions=[FilterCondition(column="customers_id", operator=">", value=100)],
            ),
        ],
        output_alias="filtered_cust",
    )
    schemas = simulate_lineage(plan, sample_catalog_tables)
    assert "id" in schemas["joined"].column_names()
    assert "customers_id" in schemas["joined"].column_names()
    assert schemas["filtered_cust"].has_column("customers_id")


def test_critical_self_join_diamond_pattern(sample_catalog_tables):
    """Tede Case 3: Diamond DAG: orders bifurcates into 2 branches, both join back together."""
    plan = PlanDraft(
        summary="Diamond DAG branching and merging",
        sources=[SourceTableRef(alias="orders", schema_name="public", table_name="orders")],
        steps=[
            FilterStep(
                target="orders",
                output_alias="completed_orders",
                conditions=[FilterCondition(column="status", operator="=", value="Completed")],
            ),
            FilterStep(
                target="orders",
                output_alias="high_value_orders",
                conditions=[FilterCondition(column="amount", operator=">", value=500)],
            ),
            JoinStep(
                left="completed_orders",
                right="high_value_orders",
                join_type="inner",
                on=[["id", "id"]],
                output_alias="merged_diamond",
            ),
        ],
        output_alias="merged_diamond",
    )
    report = verify_plan(plan, sample_catalog_tables, dialect="postgres")
    assert report.is_valid is True
    assert report.compiled_sql is not None
    assert "completed_orders" in report.compiled_sql
    assert "high_value_orders" in report.compiled_sql
    assert "merged_diamond" in report.compiled_sql


def test_critical_chain_rename_cast_filter_lineage(sample_catalog_tables):
    """Tede Case 4: Deep transform chain: Rename column, Cast it, Aggregate it, then verify old name fails."""
    plan = PlanDraft(
        summary="Rename -> Cast -> Aggregate lineage tracking",
        sources=[SourceTableRef(alias="orders", schema_name="public", table_name="orders")],
        steps=[
            RenameStep(
                target="orders",
                output_alias="renamed",
                mapping={"amount": "order_value"},
            ),
            CastStep(
                target="renamed",
                output_alias="casted",
                mapping={"order_value": "float"},
            ),
            AggregateStep(
                target="casted",
                output_alias="aggregated",
                group_by=["customer_id"],
                aggregations=[
                    AggregationSpec(column="order_value", function="sum", alias="total_customer_spend"),
                ],
            ),
            # Downstream attempts to use old 'amount' -> must fail with typo hint
            FilterStep(
                target="aggregated",
                output_alias="final",
                conditions=[FilterCondition(column="amount", operator=">", value=100)],
            ),
        ],
        output_alias="final",
    )
    with pytest.raises(LineageValidationError) as exc:
        simulate_lineage(plan, sample_catalog_tables)
    assert "Filter column 'amount' does not exist in 'aggregated'" in str(exc.value)


def test_critical_sql_injection_attempt_in_filter(sample_catalog_tables):
    """Tede Case 5: AST Validator blocks destructive injection statements inside filter parameters."""
    plan = PlanDraft(
        summary="SQL Injection defense test",
        sources=[SourceTableRef(alias="orders", schema_name="public", table_name="orders")],
        steps=[
            FilterStep(
                target="orders",
                output_alias="injected",
                conditions=[
                    FilterCondition(column="status", operator="=", value="Completed'; DROP TABLE orders; --")
                ],
            )
        ],
        output_alias="injected",
    )
    report = verify_plan(plan, sample_catalog_tables, dialect="postgres")
    # Plan must remain parameterized or safely escaped as SELECT query only
    assert report.is_valid is True
    assert "DROP TABLE" not in report.compiled_sql or ":p" in report.compiled_sql


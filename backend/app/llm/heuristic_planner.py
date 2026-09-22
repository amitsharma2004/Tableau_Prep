"""Rule-based smart fallback planner when no external LLM API key is configured.
Translates typical data prep natural language prompts against introspected schema
into valid, fully structured PlanDraft pipelines.
"""
from __future__ import annotations

import re
from app.llm.context import SampleContext, SchemaContext
from app.llm.plan_schema import (
    AggregateStep,
    AggregationSpec,
    DropNullsStep,
    FilterCondition,
    FilterStep,
    JoinStep,
    PlanDraft,
    SourceTableRef,
)


def generate_heuristic_plan(
    nl_request: str,
    schema: SchemaContext,
    samples: SampleContext,
) -> PlanDraft:
    prompt_lower = nl_request.lower()
    table_names = [t.name for t in schema.tables]

    # Find mentioned tables
    mentioned_tables = [t for t in table_names if t.lower() in prompt_lower]
    if not mentioned_tables:
        # Default to first 2 tables if available, or first table
        mentioned_tables = table_names[:2] if len(table_names) >= 2 else table_names[:1]

    sources = [
        SourceTableRef(alias=t, schema_name="main", table_name=t)
        for t in mentioned_tables
    ]

    steps = []
    current_alias = mentioned_tables[0]

    # 1. Filter condition heuristic
    if "completed" in prompt_lower and "orders" in mentioned_tables:
        filter_alias = "completed_orders"
        steps.append(
            FilterStep(
                target="orders",
                output_alias=filter_alias,
                conditions=[FilterCondition(column="status", operator="=", value="Completed")],
                logic="and",
            )
        )
        current_alias = filter_alias

    # 2. Join heuristic
    remaining_tables = [t for t in mentioned_tables if t != "orders"]
    for t in remaining_tables:
        join_output = f"{current_alias}_{t}_joined"
        # Find join key
        join_key = "customer_id" if "customer_id" in [c.name for col_list in [t_obj.columns for t_obj in schema.tables if t_obj.name == t] for c in col_list] else "product_id"
        if t == "order_items":
            join_key = "order_id"
        elif t == "customers":
            join_key = "customer_id"
        elif t == "products":
            join_key = "product_id"

        steps.append(
            JoinStep(
                left=current_alias,
                right=t,
                join_type="inner",
                on=[[join_key, join_key]],
                output_alias=join_output,
            )
        )
        current_alias = join_output

    # 3. Drop nulls heuristic
    if "drop null" in prompt_lower or "remove null" in prompt_lower or "null" in prompt_lower:
        drop_alias = f"{current_alias}_clean"
        cols_to_check = []
        if "email" in prompt_lower or "customer" in prompt_lower:
            cols_to_check.append("email")
        if "category" in prompt_lower or "product" in prompt_lower:
            cols_to_check.append("category")
        if not cols_to_check:
            cols_to_check = ["order_id"] if "orders" in mentioned_tables else ["customer_id"]

        steps.append(
            DropNullsStep(
                target=current_alias,
                output_alias=drop_alias,
                columns=cols_to_check,
            )
        )
        current_alias = drop_alias

    # 4. Aggregate heuristic
    if "aggregate" in prompt_lower or "group by" in prompt_lower or "total" in prompt_lower or "sum" in prompt_lower:
        agg_alias = "final_summary"
        group_cols = []
        if "category" in prompt_lower or "products" in mentioned_tables:
            group_cols = ["category", "sub_category"]
        elif "city" in prompt_lower or "state" in prompt_lower:
            group_cols = ["city", "state"]
        else:
            group_cols = ["status"] if "orders" in mentioned_tables else ["segment"]

        aggregations = [
            AggregationSpec(column="quantity", function="sum", alias="total_quantity")
            if "order_items" in mentioned_tables else
            AggregationSpec(column="shipping_cost", function="sum", alias="total_shipping")
            if "orders" in mentioned_tables else
            AggregationSpec(column="customer_id", function="count", alias="total_count")
        ]

        steps.append(
            AggregateStep(
                target=current_alias,
                output_alias=agg_alias,
                group_by=group_cols,
                aggregations=aggregations,
            )
        )
        current_alias = agg_alias

    # Fallback if no steps generated
    if not steps:
        steps.append(
            FilterStep(
                target=sources[0].alias,
                output_alias="filtered_data",
                conditions=[],
                logic="and",
            )
        )
        current_alias = "filtered_data"

    summary = f"Automated transformation pipeline based on: '{nl_request}'"

    return PlanDraft(
        summary=summary,
        sources=sources,
        steps=steps,
        output_alias=current_alias,
    )

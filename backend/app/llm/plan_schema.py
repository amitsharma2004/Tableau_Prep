"""The structured plan JSON contract Claude must fill in.

Every step names its inputs/outputs by `alias`, not by raw table name, so a
plan reads as a small pipeline: sources -> steps -> output_alias. This is
also the exact contract `transform/plan_to_sql.py` (milestone 5) compiles
against, so it doubles as the SQL-compiler's input format.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

FilterOperator = Literal["=", "!=", ">", "<", ">=", "<=", "is_null", "is_not_null", "in"]
JoinType = Literal["inner", "left", "right", "full"]
AggFunction = Literal["sum", "avg", "count", "min", "max"]


class SourceTableRef(BaseModel):
    alias: str = Field(description="Short name this table is referred to as in later steps, e.g. 'orders'")
    schema_name: str = Field(description="Database schema the table lives in")
    table_name: str = Field(description="Actual table name")


class FilterCondition(BaseModel):
    column: str
    operator: FilterOperator
    value: Any | None = None


class FilterStep(BaseModel):
    type: Literal["filter"] = "filter"
    target: str = Field(description="Alias of the dataset to filter")
    output_alias: str = Field(description="Alias the filtered result is stored as")
    conditions: list[FilterCondition]
    logic: Literal["and", "or"] = "and"


class DropNullsStep(BaseModel):
    type: Literal["drop_nulls"] = "drop_nulls"
    target: str
    output_alias: str
    columns: list[str] = Field(description="Rows with a null in any of these columns are removed")


class DedupeStep(BaseModel):
    type: Literal["dedupe"] = "dedupe"
    target: str
    output_alias: str
    columns: list[str] | None = Field(default=None, description="None means dedupe on all columns")


class JoinStep(BaseModel):
    type: Literal["join"] = "join"
    left: str = Field(description="Alias of the left-hand dataset")
    right: str = Field(description="Alias of the right-hand dataset")
    join_type: JoinType
    on: list[list[str]] = Field(description="List of [left_column, right_column] equality pairs")
    output_alias: str


class RenameStep(BaseModel):
    type: Literal["rename"] = "rename"
    target: str
    output_alias: str
    mapping: dict[str, str] = Field(description="old_column_name -> new_column_name")


class SelectColumnsStep(BaseModel):
    type: Literal["select_columns"] = "select_columns"
    target: str
    output_alias: str
    columns: list[str]


class AggregationSpec(BaseModel):
    column: str
    function: AggFunction
    alias: str


class AggregateStep(BaseModel):
    type: Literal["aggregate"] = "aggregate"
    target: str
    output_alias: str
    group_by: list[str]
    aggregations: list[AggregationSpec]


PlanStep = Annotated[
    Union[
        FilterStep,
        DropNullsStep,
        DedupeStep,
        JoinStep,
        RenameStep,
        SelectColumnsStep,
        AggregateStep,
    ],
    Field(discriminator="type"),
]


class PlanDraft(BaseModel):
    """The full structured plan. `steps` execute in list order; each step
    consumes datasets by alias (either a `sources[].alias` or an earlier
    step's `output_alias`) and produces a new alias. `output_alias` names
    the final result that gets written to the Hyper extract."""

    summary: str = Field(description="Plain-English explanation of the plan, shown to the human reviewer")
    sources: list[SourceTableRef]
    steps: list[PlanStep]
    output_alias: str = Field(description="Alias of the final dataset to extract")

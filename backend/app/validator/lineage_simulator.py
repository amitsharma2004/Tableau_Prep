"""Virtual column propagation simulator: simulates output schemas across the transformation DAG,
tracking columns, detecting missing columns, pruned columns, and type drift."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from app.connectors.base import TableInfo
from app.core.errors import DomainError
from app.llm.plan_schema import PlanDraft, PlanStep


class LineageValidationError(DomainError):
    """Raised when a step references a column that does not exist in its input schema."""
    def __init__(self, message: str, step_alias: str, missing_column: str, available_columns: list[str]):
        suggestions = difflib.get_close_matches(missing_column, available_columns, n=2, cutoff=0.5)
        suggestion_str = f" Did you mean: {', '.join(repr(s) for s in suggestions)}?" if suggestions else ""
        full_msg = f"Step '{step_alias}' error: {message}{suggestion_str}"
        super().__init__(full_msg)
        self.step_alias = step_alias
        self.missing_column = missing_column
        self.available_columns = available_columns
        self.suggestions = suggestions


@dataclass
class ColumnMeta:
    name: str
    data_type: str = "string"
    nullable: bool = True
    origin_table: Optional[str] = None


@dataclass
class VirtualSchema:
    alias: str
    columns: Dict[str, ColumnMeta] = field(default_factory=dict)

    def column_names(self) -> list[str]:
        return list(self.columns.keys())

    def has_column(self, col: str) -> bool:
        return col.lower() in {c.lower(): c for c in self.columns}

    def get_column(self, col: str) -> Optional[ColumnMeta]:
        for k, v in self.columns.items():
            if k.lower() == col.lower():
                return v
        return None


def simulate_lineage(
    plan: PlanDraft,
    live_tables: list[TableInfo],
) -> dict[str, VirtualSchema]:
    """Simulates column propagation across the pipeline DAG.
    
    Returns:
        dict mapping node alias -> VirtualSchema with available columns.
    Raises:
        LineageValidationError: if any step accesses non-existent/pruned column.
    """
    table_lookup: dict[tuple[str, str], TableInfo] = {
        (t.schema.lower(), t.name.lower()): t for t in live_tables
    }
    schemas: dict[str, VirtualSchema] = {}

    # 1. Initialize schemas from sources
    for src in plan.sources:
        key = (src.schema_name.lower(), src.table_name.lower())
        t_info = table_lookup.get(key)
        
        cols: dict[str, ColumnMeta] = {}
        if t_info:
            for c in t_info.columns:
                cols[c.name] = ColumnMeta(
                    name=c.name,
                    data_type=c.data_type,
                    nullable=c.nullable,
                    origin_table=src.table_name,
                )
        else:
            # Fallback if table not in introspected list: create empty/placeholder schema
            cols["id"] = ColumnMeta(name="id", data_type="integer", origin_table=src.table_name)

        schemas[src.alias] = VirtualSchema(alias=src.alias, columns=cols)

    # 2. Propagate through steps in order
    for step in plan.steps:
        out_alias = step.output_alias
        step_type = step.type

        if step_type == "join":
            left_schema = schemas.get(step.left)
            right_schema = schemas.get(step.right)
            if not left_schema:
                raise DomainError(f"Join step '{out_alias}' left input '{step.left}' not found.")
            if not right_schema:
                raise DomainError(f"Join step '{out_alias}' right input '{step.right}' not found.")

            # Validate join keys
            for left_col, right_col in step.on:
                if not left_schema.has_column(left_col):
                    raise LineageValidationError(
                        f"Left join key '{left_col}' not found in '{step.left}'.",
                        step_alias=out_alias,
                        missing_column=left_col,
                        available_columns=left_schema.column_names(),
                    )
                if not right_schema.has_column(right_col):
                    raise LineageValidationError(
                        f"Right join key '{right_col}' not found in '{step.right}'.",
                        step_alias=out_alias,
                        missing_column=right_col,
                        available_columns=right_schema.column_names(),
                    )

            # Combine columns: preserve left, add non-colliding or suffixed right columns
            merged_cols: dict[str, ColumnMeta] = dict(left_schema.columns)
            for r_name, r_meta in right_schema.columns.items():
                if r_name in merged_cols:
                    # Rename colliding column or keep alias prefixed
                    merged_cols[f"{step.right}_{r_name}"] = r_meta
                else:
                    merged_cols[r_name] = r_meta

            schemas[out_alias] = VirtualSchema(alias=out_alias, columns=merged_cols)

        elif step_type == "union":
            # All input schemas must be present
            input_schemas = [schemas[inp] for inp in step.inputs if inp in schemas]
            if not input_schemas:
                raise DomainError(f"Union step '{out_alias}' has no valid input schemas.")
            
            # Common columns in union
            first_schema = input_schemas[0]
            schemas[out_alias] = VirtualSchema(alias=out_alias, columns=dict(first_schema.columns))

        else:
            in_schema = schemas.get(step.target)
            if not in_schema:
                raise DomainError(f"Step '{out_alias}' target input '{step.target}' not found.")

            if step_type == "filter":
                for cond in step.conditions:
                    if not in_schema.has_column(cond.column):
                        raise LineageValidationError(
                            f"Filter column '{cond.column}' does not exist in '{step.target}'.",
                            step_alias=out_alias,
                            missing_column=cond.column,
                            available_columns=in_schema.column_names(),
                        )
                schemas[out_alias] = VirtualSchema(alias=out_alias, columns=dict(in_schema.columns))

            elif step_type == "drop_nulls":
                for col in step.columns:
                    if not in_schema.has_column(col):
                        raise LineageValidationError(
                            f"Drop-nulls column '{col}' does not exist in '{step.target}'.",
                            step_alias=out_alias,
                            missing_column=col,
                            available_columns=in_schema.column_names(),
                        )
                schemas[out_alias] = VirtualSchema(alias=out_alias, columns=dict(in_schema.columns))

            elif step_type == "dedupe":
                if step.columns:
                    for col in step.columns:
                        if not in_schema.has_column(col):
                            raise LineageValidationError(
                                f"Dedupe column '{col}' does not exist in '{step.target}'.",
                                step_alias=out_alias,
                                missing_column=col,
                                available_columns=in_schema.column_names(),
                            )
                schemas[out_alias] = VirtualSchema(alias=out_alias, columns=dict(in_schema.columns))

            elif step_type == "rename":
                out_cols = dict(in_schema.columns)
                for old_c, new_c in step.mapping.items():
                    if not in_schema.has_column(old_c):
                        raise LineageValidationError(
                            f"Cannot rename column '{old_c}': column does not exist in '{step.target}'.",
                            step_alias=out_alias,
                            missing_column=old_c,
                            available_columns=in_schema.column_names(),
                        )
                    meta = out_cols.pop(old_c, ColumnMeta(name=new_c))
                    out_cols[new_c] = ColumnMeta(
                        name=new_c,
                        data_type=meta.data_type,
                        nullable=meta.nullable,
                        origin_table=meta.origin_table,
                    )
                schemas[out_alias] = VirtualSchema(alias=out_alias, columns=out_cols)

            elif step_type == "select_columns":
                out_cols = {}
                for col in step.columns:
                    if not in_schema.has_column(col):
                        raise LineageValidationError(
                            f"Selected column '{col}' does not exist in '{step.target}'.",
                            step_alias=out_alias,
                            missing_column=col,
                            available_columns=in_schema.column_names(),
                        )
                    out_cols[col] = in_schema.get_column(col) or ColumnMeta(name=col)
                schemas[out_alias] = VirtualSchema(alias=out_alias, columns=out_cols)

            elif step_type == "aggregate":
                out_cols = {}
                # Validate group by
                for g_col in step.group_by:
                    if not in_schema.has_column(g_col):
                        raise LineageValidationError(
                            f"Group-by column '{g_col}' does not exist in '{step.target}'.",
                            step_alias=out_alias,
                            missing_column=g_col,
                            available_columns=in_schema.column_names(),
                        )
                    out_cols[g_col] = in_schema.get_column(g_col) or ColumnMeta(name=g_col)

                # Validate aggregation columns
                for agg in step.aggregations:
                    if agg.column != "*" and not in_schema.has_column(agg.column):
                        raise LineageValidationError(
                            f"Aggregate function '{agg.function}' column '{agg.column}' does not exist in '{step.target}'.",
                            step_alias=out_alias,
                            missing_column=agg.column,
                            available_columns=in_schema.column_names(),
                        )
                    out_cols[agg.alias] = ColumnMeta(
                        name=agg.alias,
                        data_type="float" if agg.function == "avg" else "integer",
                    )
                schemas[out_alias] = VirtualSchema(alias=out_alias, columns=out_cols)

            elif step_type == "cast":
                out_cols = dict(in_schema.columns)
                for col, target_type in step.mapping.items():
                    if not in_schema.has_column(col):
                        raise LineageValidationError(
                            f"Cast column '{col}' does not exist in '{step.target}'.",
                            step_alias=out_alias,
                            missing_column=col,
                            available_columns=in_schema.column_names(),
                        )
                    orig = out_cols.get(col, ColumnMeta(name=col))
                    out_cols[col] = ColumnMeta(
                        name=col,
                        data_type=target_type,
                        nullable=orig.nullable,
                        origin_table=orig.origin_table,
                    )
                schemas[out_alias] = VirtualSchema(alias=out_alias, columns=out_cols)

            elif step_type == "text_clean":
                for col in step.operations:
                    if not in_schema.has_column(col):
                        raise LineageValidationError(
                            f"Text-clean column '{col}' does not exist in '{step.target}'.",
                            step_alias=out_alias,
                            missing_column=col,
                            available_columns=in_schema.column_names(),
                        )
                schemas[out_alias] = VirtualSchema(alias=out_alias, columns=dict(in_schema.columns))

            else:
                schemas[out_alias] = VirtualSchema(alias=out_alias, columns=dict(in_schema.columns))

    return schemas

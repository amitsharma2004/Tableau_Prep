"""Compiles an approved PlanDraft into a single parameterized SQL SELECT.

Every step becomes one CTE, referencing either a source table or an earlier
step's CTE by the plan's own alias. All identifiers (table/schema/column/
alias names) go through `quote_identifier()` - the only untrusted string
that could otherwise reach raw SQL text. Filter *values* are always bound
parameters (`:p0`, `:p1`, ...), never inlined into the SQL string.

This is pure compilation - it never touches a database. Validation (schema
drift, SELECT-only enforcement, EXPLAIN dry-run) happens in validators.py /
executor.py, which call this first.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.connectors.base import quote_identifier
from app.core.errors import SQLValidationError
from app.llm.plan_schema import (
    AggregateStep,
    DedupeStep,
    DropNullsStep,
    FilterStep,
    JoinStep,
    PlanDraft,
    PlanStep,
    RenameStep,
    SelectColumnsStep,
)

_OPERATOR_SQL = {"=": "=", "!=": "<>", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
_JOIN_KEYWORD = {"inner": "INNER", "left": "LEFT", "right": "RIGHT", "full": "FULL"}


@dataclass
class CompiledSQL:
    sql: str
    params: dict[str, object] = field(default_factory=dict)


class _Compiler:
    def __init__(self, plan: PlanDraft):
        self.plan = plan
        self.table_refs: dict[str, str] = {}
        self.defined: set[str] = set()
        self.ctes: list[str] = []
        self.params: dict[str, object] = {}
        self._param_counter = 0

    def _next_param(self, value: object) -> str:
        name = f"p{self._param_counter}"
        self._param_counter += 1
        self.params[name] = value
        return name

    def _resolve(self, alias: str) -> str:
        if alias in self.table_refs:
            return self.table_refs[alias]
        if alias in self.defined:
            return quote_identifier(alias)
        raise SQLValidationError(f"Plan references unknown alias {alias!r}")

    def _register_sources(self) -> None:
        seen_aliases: set[str] = set()
        for src in self.plan.sources:
            if src.alias in seen_aliases:
                raise SQLValidationError(f"Duplicate source alias {src.alias!r}")
            seen_aliases.add(src.alias)
            self.table_refs[src.alias] = f"{quote_identifier(src.schema_name)}.{quote_identifier(src.table_name)}"

    def _condition_sql(self, target_alias: str, cond) -> str:
        col = f"{quote_identifier(target_alias)}.{quote_identifier(cond.column)}"
        if cond.operator == "is_null":
            return f"{col} IS NULL"
        if cond.operator == "is_not_null":
            return f"{col} IS NOT NULL"
        if cond.operator == "in":
            if not isinstance(cond.value, list) or not cond.value:
                raise SQLValidationError(f"'in' filter on {cond.column!r} requires a non-empty list value")
            placeholders = [f":{self._next_param(v)}" for v in cond.value]
            return f"{col} IN ({', '.join(placeholders)})"
        if cond.operator not in _OPERATOR_SQL:
            raise SQLValidationError(f"Unsupported filter operator: {cond.operator!r}")
        if cond.value is None:
            raise SQLValidationError(f"Filter on {cond.column!r} with operator {cond.operator!r} requires a value")
        param = self._next_param(cond.value)
        return f"{col} {_OPERATOR_SQL[cond.operator]} :{param}"

    def _compile_join(self, step: JoinStep) -> str:
        left_ref = self._resolve(step.left)
        right_ref = self._resolve(step.right)
        if not step.on:
            raise SQLValidationError(f"Join step '{step.output_alias}' has no join keys")

        on_clauses = []
        for pair in step.on:
            if len(pair) != 2:
                raise SQLValidationError(f"Join step '{step.output_alias}' has a malformed key pair: {pair!r}")
            lcol, rcol = pair
            on_clauses.append(
                f"{quote_identifier(step.left)}.{quote_identifier(lcol)} = "
                f"{quote_identifier(step.right)}.{quote_identifier(rcol)}"
            )

        join_kw = _JOIN_KEYWORD[step.join_type]
        return (
            f"SELECT * FROM {left_ref} AS {quote_identifier(step.left)} "
            f"{join_kw} JOIN {right_ref} AS {quote_identifier(step.right)} "
            f"ON {' AND '.join(on_clauses)}"
        )

    def _compile_filter(self, step: FilterStep) -> str:
        target_ref = self._resolve(step.target)
        if not step.conditions:
            raise SQLValidationError(f"Filter step '{step.output_alias}' has no conditions")
        clauses = [self._condition_sql(step.target, c) for c in step.conditions]
        joiner = " AND " if step.logic == "and" else " OR "
        return f"SELECT * FROM {target_ref} AS {quote_identifier(step.target)} WHERE {joiner.join(clauses)}"

    def _compile_drop_nulls(self, step: DropNullsStep) -> str:
        target_ref = self._resolve(step.target)
        if not step.columns:
            raise SQLValidationError(f"drop_nulls step '{step.output_alias}' has no columns")
        clauses = [f"{quote_identifier(step.target)}.{quote_identifier(c)} IS NOT NULL" for c in step.columns]
        return f"SELECT * FROM {target_ref} AS {quote_identifier(step.target)} WHERE {' AND '.join(clauses)}"

    def _compile_dedupe(self, step: DedupeStep) -> str:
        target_ref = self._resolve(step.target)
        target_sql = quote_identifier(step.target)
        if step.columns:
            # ANSI-portable dedupe-on-columns via a window function (DISTINCT
            # ON is Postgres-only and wouldn't work for the MySQL connector).
            # Known limitation: the output retains a synthetic __rn column.
            partition_cols = ", ".join(f"{target_sql}.{quote_identifier(c)}" for c in step.columns)
            return (
                f"SELECT * FROM ("
                f"SELECT {target_sql}.*, ROW_NUMBER() OVER (PARTITION BY {partition_cols} ORDER BY (SELECT 1)) AS __rn "
                f"FROM {target_ref} AS {target_sql}"
                f") AS __deduped WHERE __rn = 1"
            )
        return f"SELECT DISTINCT * FROM {target_ref} AS {target_sql}"

    def _compile_rename(self, step: RenameStep) -> str:
        target_ref = self._resolve(step.target)
        if not step.mapping:
            raise SQLValidationError(f"rename step '{step.output_alias}' has an empty mapping")
        select_cols = ", ".join(
            f"{quote_identifier(step.target)}.{quote_identifier(old)} AS {quote_identifier(new)}"
            for old, new in step.mapping.items()
        )
        return f"SELECT {select_cols} FROM {target_ref} AS {quote_identifier(step.target)}"

    def _compile_select_columns(self, step: SelectColumnsStep) -> str:
        target_ref = self._resolve(step.target)
        if not step.columns:
            raise SQLValidationError(f"select_columns step '{step.output_alias}' has no columns")
        select_cols = ", ".join(f"{quote_identifier(step.target)}.{quote_identifier(c)}" for c in step.columns)
        return f"SELECT {select_cols} FROM {target_ref} AS {quote_identifier(step.target)}"

    def _compile_aggregate(self, step: AggregateStep) -> str:
        target_ref = self._resolve(step.target)
        target_sql = quote_identifier(step.target)
        if not step.aggregations:
            raise SQLValidationError(f"aggregate step '{step.output_alias}' has no aggregations")
        group_cols = [f"{target_sql}.{quote_identifier(c)}" for c in step.group_by]
        agg_exprs = [
            f"{agg.function.upper()}({target_sql}.{quote_identifier(agg.column)}) AS {quote_identifier(agg.alias)}"
            for agg in step.aggregations
        ]
        select_list = ", ".join(group_cols + agg_exprs)
        group_by_sql = f" GROUP BY {', '.join(group_cols)}" if group_cols else ""
        return f"SELECT {select_list} FROM {target_ref} AS {target_sql}{group_by_sql}"

    def _compile_step(self, step: PlanStep) -> str:
        if isinstance(step, JoinStep):
            return self._compile_join(step)
        if isinstance(step, FilterStep):
            return self._compile_filter(step)
        if isinstance(step, DropNullsStep):
            return self._compile_drop_nulls(step)
        if isinstance(step, DedupeStep):
            return self._compile_dedupe(step)
        if isinstance(step, RenameStep):
            return self._compile_rename(step)
        if isinstance(step, SelectColumnsStep):
            return self._compile_select_columns(step)
        if isinstance(step, AggregateStep):
            return self._compile_aggregate(step)
        raise SQLValidationError(f"Unsupported step type: {step.type!r}")  # pragma: no cover - schema prevents this

    def compile(self, target_alias: str | None = None) -> CompiledSQL:
        self._register_sources()

        stop_alias = target_alias or self.plan.output_alias

        for step in self.plan.steps:
            if step.output_alias in self.table_refs or step.output_alias in self.defined:
                raise SQLValidationError(f"Step output_alias {step.output_alias!r} collides with an earlier alias")
            body = self._compile_step(step)
            self.ctes.append(f"{quote_identifier(step.output_alias)} AS ({body})")
            self.defined.add(step.output_alias)
            if step.output_alias == stop_alias:
                break

        if stop_alias not in self.defined and stop_alias not in self.table_refs:
            raise SQLValidationError(
                f"Requested alias {stop_alias!r} is not produced by any step or source"
            )

        final_ref = self._resolve(stop_alias)
        sql = f"WITH {', '.join(self.ctes)} SELECT * FROM {final_ref}" if self.ctes else f"SELECT * FROM {final_ref}"

        return CompiledSQL(sql=sql, params=self.params)


def compile_plan(plan: PlanDraft, target_alias: str | None = None) -> CompiledSQL:
    return _Compiler(plan).compile(target_alias=target_alias)

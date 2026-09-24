"""Confidence Scorer: Evaluates transformation reliability, schema grounding certainty,
and risk of join fan-out / unexpected row drops."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal

from app.connectors.base import TableInfo
from app.llm.plan_schema import PlanDraft, PlanStep


ConfidenceLevel = Literal["high", "medium", "low"]


@dataclass
class AnomalyWarning:
    level: Literal["warning", "info"]
    step_alias: str
    message: str


@dataclass
class ConfidenceReport:
    overall_score: int  # 0 to 100
    level: ConfidenceLevel
    grounding_score: int
    join_integrity_score: int
    complexity_score: int
    warnings: list[AnomalyWarning] = field(default_factory=list)


def score_plan_confidence(
    plan: PlanDraft,
    live_tables: list[TableInfo],
) -> ConfidenceReport:
    """Calculates multidimensional confidence score for a proposed flow plan."""
    score = 100
    warnings: list[AnomalyWarning] = []

    table_map = {f"{t.schema.lower()}.{t.name.lower()}": t for t in live_tables}
    table_map.update({t.name.lower(): t for t in live_tables})

    # 1. Grounding Score (Check sources exact match)
    grounding_deductions = 0
    for src in plan.sources:
        full_name = f"{src.schema_name.lower()}.{src.table_name.lower()}"
        if full_name not in table_map and src.table_name.lower() not in table_map:
            grounding_deductions += 25
            warnings.append(
                AnomalyWarning(
                    level="warning",
                    step_alias=src.alias,
                    message=f"Source table '{src.schema_name}.{src.table_name}' was not found directly in catalog schema.",
                )
            )

    grounding_score = max(0, 100 - grounding_deductions)
    score -= (100 - grounding_score) * 0.4

    # 2. Join Integrity & Fan-Out Risk Score
    join_deductions = 0
    for step in plan.steps:
        if step.type == "join":
            # Check for multi-column vs single column join
            if len(step.on) == 0:
                join_deductions += 40
                warnings.append(
                    AnomalyWarning(
                        level="warning",
                        step_alias=step.output_alias,
                        message="Cartesian Cross Join detected (no ON conditions). High risk of row explosion!",
                    )
                )
            
            # Non-equality or loose join check
            for l_col, r_col in step.on:
                if l_col.lower() != r_col.lower() and not (
                    l_col.lower().endswith("id") or r_col.lower().endswith("id")
                ):
                    join_deductions += 10
                    warnings.append(
                        AnomalyWarning(
                            level="info",
                            step_alias=step.output_alias,
                            message=f"Join on '{l_col} = {r_col}' matches non-standard ID naming; verify business key intent.",
                        )
                    )

            if step.join_type == "full":
                join_deductions += 15
                warnings.append(
                    AnomalyWarning(
                        level="info",
                        step_alias=step.output_alias,
                        message="FULL OUTER JOIN produces high null volume in unmatched keys.",
                    )
                )

    join_integrity_score = max(0, 100 - join_deductions)
    score -= (100 - join_integrity_score) * 0.35

    # 3. Pipeline Complexity & Length Score
    complexity_deductions = 0
    if len(plan.steps) > 8:
        complexity_deductions += 15
        warnings.append(
            AnomalyWarning(
                level="info",
                step_alias=plan.output_alias,
                message=f"Deep pipeline ({len(plan.steps)} steps). Recommend verifying intermediate step previews.",
            )
        )

    # Cast risk (strings to dates or numbers can cause runtime parse failures)
    for step in plan.steps:
        if step.type == "cast":
            for col, t_type in step.mapping.items():
                if t_type in ("date", "integer", "float"):
                    complexity_deductions += 5

    complexity_score = max(0, 100 - complexity_deductions)
    score -= (100 - complexity_score) * 0.25

    final_score = max(10, min(100, int(round(score))))

    if final_score >= 85:
        level: ConfidenceLevel = "high"
    elif final_score >= 65:
        level = "medium"
    else:
        level = "low"

    return ConfidenceReport(
        overall_score=final_score,
        level=level,
        grounding_score=grounding_score,
        join_integrity_score=join_integrity_score,
        complexity_score=complexity_score,
        warnings=warnings,
    )

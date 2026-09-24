"""Master Plan Verifier: combines DAG topology verification, virtual schema lineage propagation,
SQL pushdown compilation dry-run, and AI confidence scoring into a single unified verification report."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from app.connectors.base import TableInfo
from app.core.errors import DomainError
from app.llm.plan_schema import PlanDraft
from app.transform.plan_to_sql import compile_plan
from app.transform.validators import validate_select_only
from app.validator.confidence_scorer import ConfidenceReport, score_plan_confidence
from app.validator.dag_checker import DAGValidationError, validate_dag
from app.validator.lineage_simulator import LineageValidationError, simulate_lineage


@dataclass
class VerificationReport:
    is_valid: bool
    confidence: ConfidenceReport
    topo_order: list[str]
    virtual_schemas: dict[str, list[str]]  # node_alias -> list of available column names
    compiled_sql: Optional[str] = None
    error_message: Optional[str] = None
    repair_feedback: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "confidence": asdict(self.confidence),
            "topo_order": self.topo_order,
            "virtual_schemas": self.virtual_schemas,
            "compiled_sql": self.compiled_sql,
            "error_message": self.error_message,
            "repair_feedback": self.repair_feedback,
        }


def verify_plan(
    plan: PlanDraft,
    live_tables: list[TableInfo],
    dialect: str = "postgres",
) -> VerificationReport:
    """Runs all 4 verification gates on a proposed PlanDraft.
    
    Returns:
        VerificationReport with full diagnostics, lineage, and confidence scoring.
    """
    # 1. Gate 1: DAG Topology & Cycle Check
    try:
        topo_order = validate_dag(plan)
    except DAGValidationError as err:
        return VerificationReport(
            is_valid=False,
            confidence=ConfidenceReport(
                overall_score=0,
                level="low",
                grounding_score=0,
                join_integrity_score=0,
                complexity_score=0,
                warnings=[],
            ),
            topo_order=[],
            virtual_schemas={},
            error_message=str(err),
            repair_feedback=f"DAG validation failed: {err}. Ensure every step references a defined upstream alias and no circular loops exist.",
        )

    # 2. Gate 2: Virtual Column Lineage Simulation
    try:
        sim_schemas = simulate_lineage(plan, live_tables)
        schemas_col_names = {k: v.column_names() for k, v in sim_schemas.items()}
    except LineageValidationError as err:
        return VerificationReport(
            is_valid=False,
            confidence=ConfidenceReport(
                overall_score=20,
                level="low",
                grounding_score=50,
                join_integrity_score=20,
                complexity_score=50,
                warnings=[],
            ),
            topo_order=topo_order,
            virtual_schemas={},
            error_message=str(err),
            repair_feedback=f"Column lineage failed at step '{err.step_alias}': column '{err.missing_column}' does not exist. Available columns in upstream: {err.available_columns}. Suggestion: {err.suggestions}",
        )
    except DomainError as err:
        return VerificationReport(
            is_valid=False,
            confidence=ConfidenceReport(
                overall_score=20,
                level="low",
                grounding_score=50,
                join_integrity_score=20,
                complexity_score=50,
                warnings=[],
            ),
            topo_order=topo_order,
            virtual_schemas={},
            error_message=str(err),
            repair_feedback=str(err),
        )

    # 3. Gate 3: Confidence & Fan-Out Anomaly Scoring
    confidence = score_plan_confidence(plan, live_tables)

    # 4. Gate 4: Pushdown SQL CTE Compilation & AST Security Check
    try:
        compiled = compile_plan(plan)
        validate_select_only(compiled.sql, dialect=dialect)
        compiled_sql_str = compiled.sql
    except Exception as err:
        return VerificationReport(
            is_valid=False,
            confidence=confidence,
            topo_order=topo_order,
            virtual_schemas=schemas_col_names,
            error_message=f"SQL compilation error: {err}",
            repair_feedback=f"Plan could not be compiled into valid SQL: {err}. Check step operations and parameters.",
        )

    return VerificationReport(
        is_valid=True,
        confidence=confidence,
        topo_order=topo_order,
        virtual_schemas=schemas_col_names,
        compiled_sql=compiled_sql_str,
        error_message=None,
        repair_feedback=None,
    )

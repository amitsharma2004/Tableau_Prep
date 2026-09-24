"""DAG validation: ensures flow pipeline forms a valid directed acyclic graph
with no disconnected steps and reachable output_alias."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Set

from app.core.errors import DomainError
from app.llm.plan_schema import PlanDraft, PlanStep


class DAGValidationError(DomainError):
    """Raised when plan has invalid graph topology (cycle, missing input, unreachable output)."""


def validate_dag(plan: PlanDraft) -> list[str]:
    """Validates the DAG structure of a PlanDraft.
    
    Returns:
        Topological order of aliases (sources + step output_aliases).
        
    Raises:
        DAGValidationError: if cycle detected, input missing, or output unreachable.
    """
    defined_aliases: Set[str] = {src.alias for src in plan.sources}
    in_degree: dict[str, int] = defaultdict(int)
    graph: dict[str, list[str]] = defaultdict(list)

    # Initialize all source nodes in graph
    for src in plan.sources:
        in_degree[src.alias] = 0

    for step in plan.steps:
        out_alias = step.output_alias
        if out_alias in defined_aliases:
            raise DAGValidationError(f"Duplicate alias '{out_alias}' defined more than once in plan.")
        defined_aliases.add(out_alias)
        in_degree[out_alias] = 0

    # Build adjacency edges: upstream -> downstream
    for step in plan.steps:
        out_alias = step.output_alias
        upstream_inputs = _get_step_inputs(step)

        for inp in upstream_inputs:
            if inp not in defined_aliases:
                raise DAGValidationError(
                    f"Step '{out_alias}' references input '{inp}' which is never defined in sources or previous steps."
                )
            graph[inp].append(out_alias)
            in_degree[out_alias] += 1

    # Kahn's Algorithm for Topological Sort & Cycle Detection
    queue = deque([node for node, deg in in_degree.items() if deg == 0])
    topo_order: list[str] = []

    while queue:
        curr = queue.popleft()
        topo_order.append(curr)

        for neighbor in graph[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(topo_order) != len(defined_aliases):
        # Nodes with in_degree > 0 are part of a cycle
        cycled = [node for node, deg in in_degree.items() if deg > 0]
        raise DAGValidationError(f"Cyclic dependency detected involving steps/aliases: {cycled}")

    # Check output_alias is reachable
    if plan.output_alias not in defined_aliases:
        raise DAGValidationError(
            f"Plan output_alias '{plan.output_alias}' is not defined by any source or step."
        )

    return topo_order


def _get_step_inputs(step: PlanStep) -> list[str]:
    """Extracts all upstream alias dependencies for a given PlanStep."""
    if step.type == "join":
        return [step.left, step.right]
    elif step.type == "union":
        return list(step.inputs)
    else:
        return [step.target]

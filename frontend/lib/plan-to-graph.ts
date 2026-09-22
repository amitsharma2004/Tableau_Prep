import { Node, Edge } from "@xyflow/react";
import type { PlanDraft, PlanStep, SourceTableRef } from "@/lib/types";

export interface PrepNodeData extends Record<string, unknown> {
  label: string;
  type: string;
  alias: string;
  description: string;
  badgeColor?: string;
  details?: Record<string, unknown>;
  columnsCount?: number;
  isSelected?: boolean;
}

const STEP_COLORS: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  source: { bg: "bg-blue-50", border: "border-blue-400", text: "text-blue-700", badge: "bg-blue-100 text-blue-800" },
  filter: { bg: "bg-amber-50", border: "border-amber-400", text: "text-amber-700", badge: "bg-amber-100 text-amber-800" },
  join: { bg: "bg-emerald-50", border: "border-emerald-400", text: "text-emerald-700", badge: "bg-emerald-100 text-emerald-800" },
  aggregate: { bg: "bg-purple-50", border: "border-purple-400", text: "text-purple-700", badge: "bg-purple-100 text-purple-800" },
  drop_nulls: { bg: "bg-rose-50", border: "border-rose-400", text: "text-rose-700", badge: "bg-rose-100 text-rose-800" },
  dedupe: { bg: "bg-indigo-50", border: "border-indigo-400", text: "text-indigo-700", badge: "bg-indigo-100 text-indigo-800" },
  rename: { bg: "bg-cyan-50", border: "border-cyan-400", text: "text-cyan-700", badge: "bg-cyan-100 text-cyan-800" },
  select_columns: { bg: "bg-teal-50", border: "border-teal-400", text: "text-teal-700", badge: "bg-teal-100 text-teal-800" },
  output: { bg: "bg-orange-50", border: "border-orange-500", text: "text-orange-800", badge: "bg-orange-100 text-orange-900" },
};

export function planToFlowGraph(plan: PlanDraft): { nodes: Node<PrepNodeData>[]; edges: Edge[] } {
  const nodes: Node<PrepNodeData>[] = [];
  const edges: Edge[] = [];

  // Alias -> position / id map
  const aliasToNodeId: Record<string, string> = {};

  // Step 1: Layout Sources vertically on the left
  const startX = 50;
  const startY = 80;
  const colWidth = 260;
  const rowHeight = 110;

  plan.sources.forEach((src: SourceTableRef, idx: number) => {
    const nodeId = `source-${src.alias}`;
    aliasToNodeId[src.alias] = nodeId;

    nodes.push({
      id: nodeId,
      type: "prepStep",
      position: { x: startX, y: startY + idx * rowHeight },
      data: {
        label: src.table_name,
        type: "source",
        alias: src.alias,
        description: `${src.schema_name}.${src.table_name}`,
        badgeColor: STEP_COLORS.source.badge,
        details: { schema: src.schema_name, table: src.table_name },
      },
    });
  });

  // Step 2: Traverse steps and position downstream
  let currentX = startX + colWidth + 60;
  const currentY = startY;

  plan.steps.forEach((step: PlanStep, idx: number) => {
    const stepType = step.type;
    const outputAlias = step.output_alias;
    const nodeId = `step-${idx}-${outputAlias}`;
    aliasToNodeId[outputAlias] = nodeId;

    let description = "";
    if (step.type === "filter") {
      description = `${step.conditions.length} condition(s) on '${step.target}'`;
    } else if (step.type === "join") {
      description = `${step.join_type.toUpperCase()} join with '${step.right}'`;
    } else if (step.type === "drop_nulls") {
      description = `Drop nulls in: ${step.columns.join(", ")}`;
    } else if (step.type === "aggregate") {
      description = `Group by ${step.group_by.join(", ") || "all"}`;
    } else if (step.type === "dedupe") {
      description = "Deduplicate rows";
    } else if (step.type === "rename") {
      const keys = Object.keys(step.mapping || {});
      description = `Rename: ${keys.slice(0, 2).map((k) => `${k} ➔ ${step.mapping[k]}`).join(", ")}`;
    } else if (step.type === "select_columns") {
      description = `Select ${step.columns.length} columns`;
    }

    // Determine Y position based on parent inputs
    let targetY = currentY;
    if (step.type === "join") {
      const leftParentId = aliasToNodeId[step.left];
      const rightParentId = aliasToNodeId[step.right];
      const leftNode = nodes.find((n) => n.id === leftParentId);
      const rightNode = nodes.find((n) => n.id === rightParentId);
      if (leftNode && rightNode) {
        targetY = (leftNode.position.y + rightNode.position.y) / 2;
      }
    }

    nodes.push({
      id: nodeId,
      type: "prepStep",
      position: { x: currentX, y: targetY },
      data: {
        label: outputAlias,
        type: stepType,
        alias: outputAlias,
        description,
        badgeColor: (STEP_COLORS[stepType] || STEP_COLORS.filter).badge,
        details: step as unknown as Record<string, unknown>,
      },
    });

    // Create Edges
    if (step.type === "join") {
      if (aliasToNodeId[step.left]) {
        edges.push({
          id: `e-${aliasToNodeId[step.left]}-${nodeId}-left`,
          source: aliasToNodeId[step.left],
          target: nodeId,
          type: "prepEdge",
          animated: true,
          style: { stroke: "#10b981", strokeWidth: 2 },
          data: { sourceAlias: step.left, targetAlias: outputAlias },
        });
      }
      if (aliasToNodeId[step.right] && aliasToNodeId[step.right] !== aliasToNodeId[step.left]) {
        edges.push({
          id: `e-${aliasToNodeId[step.right]}-${nodeId}-right`,
          source: aliasToNodeId[step.right],
          target: nodeId,
          type: "prepEdge",
          animated: true,
          style: { stroke: "#10b981", strokeWidth: 2 },
          data: { sourceAlias: step.right, targetAlias: outputAlias },
        });
      }
    } else if ("target" in step && step.target && aliasToNodeId[step.target]) {
      edges.push({
        id: `e-${aliasToNodeId[step.target]}-${nodeId}`,
        source: aliasToNodeId[step.target],
        target: nodeId,
        type: "prepEdge",
        animated: true,
        style: { stroke: "#6366f1", strokeWidth: 2 },
        data: { sourceAlias: (step as any).target, targetAlias: outputAlias },
      });
    }

    currentX += colWidth;
  });

  // Step 3: Add Final Output Node
  const finalOutputAlias = plan.output_alias;
  const parentNodeId = aliasToNodeId[finalOutputAlias];
  if (parentNodeId) {
    const parentNode = nodes.find((n) => n.id === parentNodeId);
    const outputNodeId = "output-final";
    nodes.push({
      id: outputNodeId,
      type: "prepStep",
      position: { x: currentX, y: parentNode ? parentNode.position.y : startY },
      data: {
        label: "Tableau Hyper Extract",
        type: "output",
        alias: finalOutputAlias,
        description: "Ready to Publish",
        badgeColor: STEP_COLORS.output.badge,
        details: { output_alias: finalOutputAlias },
      },
    });

    edges.push({
      id: `e-${parentNodeId}-${outputNodeId}`,
      source: parentNodeId,
      target: outputNodeId,
      type: "prepEdge",
      animated: true,
      style: { stroke: "#ea580c", strokeWidth: 3 },
      data: { sourceAlias: finalOutputAlias, targetAlias: "output" },
    });
  }

  return { nodes, edges };
}

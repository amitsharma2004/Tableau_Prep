"use client";

import React, { useMemo, useCallback, useState } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  Connection as FlowConnection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { PlanDraft } from "@/lib/types";
import { planToFlowGraph, PrepNodeData } from "@/lib/plan-to-graph";
import { PrepStepNode } from "@/components/prep-step-node";
import { PrepFlowEdge } from "@/components/prep-flow-edge";

const nodeTypes = {
  prepStep: PrepStepNode,
};

const edgeTypes = {
  prepEdge: PrepFlowEdge,
};

export interface VisualFlowCanvasProps {
  plan: PlanDraft;
  onNodeSelect?: (nodeData: PrepNodeData | null) => void;
  onTableDrop?: (tableName: string) => void;
  onConnectNodes?: (sourceAlias: string, targetAlias: string) => void;
  onAddStepOnEdge?: (sourceAlias: string, targetAlias: string) => void;
  onDeleteStep?: (alias: string) => void;
  className?: string;
}

export function VisualFlowCanvas({
  plan,
  onNodeSelect,
  onTableDrop,
  onConnectNodes,
  onAddStepOnEdge,
  onDeleteStep,
  className = "h-[440px]",
}: VisualFlowCanvasProps) {
  const { initialNodes, initialEdges } = useMemo(() => {
    const { nodes, edges } = planToFlowGraph(plan);
    // Inject onDeleteStep handler into intermediate step nodes
    const nodesWithHandler = nodes.map((n) => ({
      ...n,
      data: {
        ...n.data,
        onDeleteStep: onDeleteStep ? (alias: string) => onDeleteStep(alias) : undefined,
      },
    }));
    // Inject onAddStep handler into custom edges
    const edgesWithHandler = edges.map((e) => ({
      ...e,
      data: {
        ...(e.data || {}),
        onAddStep: (src: string, tgt: string) => onAddStepOnEdge?.(src, tgt),
      },
    }));
    return { initialNodes: nodesWithHandler, initialEdges: edgesWithHandler };
  }, [plan, onAddStepOnEdge, onDeleteStep]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [isDragOver, setIsDragOver] = useState(false);

  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Handle Edge Connection drag from one table/step node to another
  const handleConnect = useCallback(
    (connection: FlowConnection) => {
      if (!connection.source || !connection.target) return;
      const sourceNode = nodes.find((n) => n.id === connection.source);
      const targetNode = nodes.find((n) => n.id === connection.target);
      if (!sourceNode || !targetNode) return;

      const sourceAlias = (sourceNode.data as PrepNodeData).alias;
      const targetAlias = (targetNode.data as PrepNodeData).alias;

      if (sourceAlias && targetAlias && sourceAlias !== targetAlias) {
        onConnectNodes?.(sourceAlias, targetAlias);
      }
    },
    [nodes, onConnectNodes]
  );

  // Drag and Drop handlers for dropping tables from sidebar onto canvas
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const tableName = e.dataTransfer.getData("application/tableau-table");
      if (tableName && onTableDrop) {
        onTableDrop(tableName);
      }
    },
    [onTableDrop]
  );

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`w-full bg-slate-50 border rounded-xl relative overflow-hidden shadow-inner transition-colors ${
        isDragOver ? "border-blue-500 ring-2 ring-blue-300 bg-blue-50/20" : "border-slate-200"
      } ${className}`}
    >
      <div className="absolute top-3 left-4 z-10 bg-white/90 backdrop-blur border border-slate-200 px-3 py-1.5 rounded-md shadow-sm flex items-center gap-2">
        <span className="text-xs font-semibold text-slate-700">Tableau Prep Workflow Canvas</span>
        <span className="text-[11px] text-slate-500">({nodes.length} nodes)</span>
        {isDragOver && (
          <span className="text-[11px] font-bold text-blue-600 animate-pulse ml-2">
            Drop table here to add to flow!
          </span>
        )}
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={handleConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={(_, node) => onNodeSelect?.(node.data as PrepNodeData)}
        onPaneClick={() => onNodeSelect?.(null)}
        fitView
        attributionPosition="bottom-right"
        minZoom={0.2}
        maxZoom={1.5}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#cbd5e1" />
        <Controls className="bg-white border border-slate-200 shadow-sm rounded" />
      </ReactFlow>
    </div>
  );
}

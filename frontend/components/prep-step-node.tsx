"use client";

import React, { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import type { PrepNodeData } from "@/lib/plan-to-graph";
import {
  Database,
  Filter,
  GitMerge,
  BarChart3,
  Trash2,
  CopyX,
  Columns,
  FileOutput,
  Tag,
  Layers,
} from "lucide-react";

function getStepIcon(type: string) {
  switch (type) {
    case "source":
      return <Database className="w-4 h-4 text-blue-600" />;
    case "filter":
      return <Filter className="w-4 h-4 text-amber-600" />;
    case "join":
      return <GitMerge className="w-4 h-4 text-emerald-600" />;
    case "union":
      return <Layers className="w-4 h-4 text-fuchsia-600" />;
    case "aggregate":
      return <BarChart3 className="w-4 h-4 text-purple-600" />;
    case "drop_nulls":
      return <Trash2 className="w-4 h-4 text-rose-600" />;
    case "dedupe":
      return <CopyX className="w-4 h-4 text-indigo-600" />;
    case "rename":
      return <Tag className="w-4 h-4 text-cyan-600" />;
    case "select_columns":
      return <Columns className="w-4 h-4 text-teal-600" />;
    case "cast":
      return <Tag className="w-4 h-4 text-violet-600" />;
    case "text_clean":
      return <Columns className="w-4 h-4 text-sky-600" />;
    case "output":
      return <FileOutput className="w-4 h-4 text-orange-600" />;
    default:
      return <Database className="w-4 h-4 text-slate-600" />;
  }
}

function PrepStepNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as PrepNodeData;
  const isSource = nodeData.type === "source";
  const isOutput = nodeData.type === "output";

  return (
    <div
      className={`min-w-[210px] max-w-[240px] bg-white rounded-lg shadow-sm border transition-all duration-200 cursor-pointer ${
        selected
          ? "border-blue-500 ring-2 ring-blue-200 shadow-md"
          : "border-slate-200 hover:border-slate-400"
      }`}
    >
      {/* Target handle (left) - available on all nodes */}
      <Handle
        type="target"
        position={Position.Left}
        className="w-2.5 h-2.5 bg-blue-500 border border-white"
      />

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 bg-slate-50/70 rounded-t-lg">
        <div className="flex items-center gap-2">
          {getStepIcon(nodeData.type)}
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
            {nodeData.type}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
              nodeData.badgeColor ?? "bg-slate-100 text-slate-600"
            }`}
          >
            {nodeData.alias}
          </span>
          {!isSource && !isOutput && nodeData.onDeleteStep && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                nodeData.onDeleteStep?.(nodeData.alias);
              }}
              title="Delete this step"
              className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-3">
        <h4 className="text-xs font-semibold text-slate-800 truncate" title={nodeData.label}>
          {nodeData.label}
        </h4>
        <p className="text-[11px] text-slate-500 mt-1 line-clamp-2" title={nodeData.description}>
          {nodeData.description}
        </p>
      </div>

      {/* Source handle (right) - not needed for output */}
      {!isOutput && (
        <Handle
          type="source"
          position={Position.Right}
          className="w-2.5 h-2.5 bg-blue-500 border border-white"
        />
      )}
    </div>
  );
}

export const PrepStepNode = memo(PrepStepNodeComponent);

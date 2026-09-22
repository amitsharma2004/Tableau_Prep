"use client";

import React from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "@xyflow/react";
import { Plus } from "lucide-react";

export interface PrepEdgeData {
  sourceAlias?: string;
  targetAlias?: string;
  onAddStep?: (sourceAlias: string, targetAlias: string) => void;
}

export function PrepFlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const edgeData = data as PrepEdgeData | undefined;

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={style} markerEnd={markerEnd} />
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: "all",
          }}
          className="nodrag nopan"
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              if (edgeData?.onAddStep && edgeData.sourceAlias && edgeData.targetAlias) {
                edgeData.onAddStep(edgeData.sourceAlias, edgeData.targetAlias);
              }
            }}
            className="group flex items-center justify-center w-6 h-6 rounded-full bg-white border-2 border-blue-500 text-blue-600 shadow-md hover:scale-125 hover:bg-blue-600 hover:text-white hover:border-blue-600 transition-all duration-150 cursor-pointer"
            title="Add Clean Step (Rename, Filter, Remove Columns, etc.)"
          >
            <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

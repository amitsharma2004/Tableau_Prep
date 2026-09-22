"use client";

import React from "react";
import {
  Filter,
  GitMerge,
  BarChart3,
  Trash2,
  CopyX,
  Columns,
  FileOutput,
  Database,
  Tag,
  ArrowRight,
  ListFilter,
  CheckCircle2,
} from "lucide-react";
import type { PrepNodeData } from "@/lib/plan-to-graph";

interface TableauStepChangesProps {
  node: PrepNodeData;
}

export function TableauStepChanges({ node }: TableauStepChangesProps) {
  const details = node.details || {};
  const stepType = node.type;

  return (
    <div className="bg-slate-50/80 border border-slate-200 rounded-lg p-3.5 mb-4 shadow-2xs">
      <div className="flex items-center justify-between border-b border-slate-200/80 pb-2 mb-2.5">
        <div className="flex items-center gap-2">
          <span className="p-1 bg-white border border-slate-200 rounded text-slate-700 shadow-2xs">
            <ListFilter className="w-3.5 h-3.5 text-blue-600" />
          </span>
          <div>
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <span>Applied Step Changes</span>
              <span className="text-[10px] lowercase px-1.5 py-0.2 bg-blue-100 text-blue-700 font-semibold rounded">
                Tableau Prep History
              </span>
            </h4>
            <span className="text-[10px] text-slate-500">
              Operations applied on alias: <strong className="text-slate-700 font-mono">{node.alias}</strong>
            </span>
          </div>
        </div>
        <span className="text-[11px] font-semibold text-slate-600 bg-white border border-slate-200 px-2 py-0.5 rounded">
          Step Type: {stepType}
        </span>
      </div>

      {/* 1. Filter Step Changes */}
      {stepType === "filter" && Boolean(details.conditions) && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-medium text-slate-600 block">
            Filter Conditions ({((details.conditions as unknown[]) || []).length} rule
            {((details.conditions as unknown[]) || []).length > 1 ? "s" : ""}, logic:{" "}
            <strong>{String(details.logic || "and").toUpperCase()}</strong>):
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            {((details.conditions as Record<string, unknown>[]) || []).map((c, i) => (
              <div
                key={i}
                className="flex items-center gap-2 bg-white border border-amber-200/80 rounded-md px-2.5 py-1.5 text-xs shadow-2xs"
              >
                <Filter className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                <div className="truncate">
                  <span className="font-semibold text-slate-800">{String(c.column)}</span>{" "}
                  <span className="text-amber-700 font-mono font-medium">{String(c.operator)}</span>{" "}
                  <span className="font-mono bg-slate-100 text-slate-800 px-1 rounded">
                    {c.value !== undefined ? String(c.value) : "NULL"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 2. Rename Step Changes */}
      {stepType === "rename" && Boolean(details.mapping) && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-medium text-slate-600 block">
            Renamed Columns ({Object.keys((details.mapping as Record<string, string>) || {}).length}):
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            {Object.entries((details.mapping as Record<string, string>) || {}).map(([oldName, newName], i) => (
              <div
                key={i}
                className="flex items-center gap-2 bg-white border border-cyan-200/80 rounded-md px-2.5 py-1.5 text-xs shadow-2xs"
              >
                <Tag className="w-3.5 h-3.5 text-cyan-600 shrink-0" />
                <span className="line-through text-slate-400 truncate">{oldName}</span>
                <ArrowRight className="w-3 h-3 text-slate-400 shrink-0" />
                <span className="font-semibold text-cyan-800 truncate">{newName}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. Join Step Changes */}
      {stepType === "join" && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-medium text-slate-600 block">
            Join Clauses ({String(details.join_type || "inner").toUpperCase()} JOIN):
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <div className="bg-white border border-emerald-200/80 rounded-md px-3 py-1.5 text-xs flex items-center gap-2 shadow-2xs">
              <GitMerge className="w-3.5 h-3.5 text-emerald-600" />
              <span>
                Left Table: <strong className="text-slate-800 font-mono">{String(details.left)}</strong>
              </span>
              <span className="text-slate-300">|</span>
              <span>
                Right Table: <strong className="text-slate-800 font-mono">{String(details.right)}</strong>
              </span>
            </div>
            {((details.on as string[][]) || []).map((pair, i) => (
              <div
                key={i}
                className="bg-emerald-50 border border-emerald-200 rounded-md px-2.5 py-1 text-xs font-mono text-emerald-900"
              >
                {String(details.left)}.{pair[0]} = {String(details.right)}.{pair[1]}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Aggregate Step Changes */}
      {stepType === "aggregate" && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-medium text-slate-600 block">
            Aggregations & Group By:
          </span>
          <div className="flex flex-wrap items-center gap-2">
            {Boolean(details.group_by) && (
              <div className="bg-white border border-purple-200/80 rounded-md px-2.5 py-1.5 text-xs flex items-center gap-1.5 shadow-2xs">
                <BarChart3 className="w-3.5 h-3.5 text-purple-600" />
                <span>
                  Group By:{" "}
                  <strong className="text-slate-800 font-mono">
                    {((details.group_by as string[]) || []).join(", ") || "none"}
                  </strong>
                </span>
              </div>
            )}
            {((details.aggregations as Record<string, string>[]) || []).map((agg, i) => (
              <div
                key={i}
                className="bg-purple-50 border border-purple-200 rounded-md px-2.5 py-1 text-xs font-mono text-purple-900"
              >
                {agg.alias}: {String(agg.function).toUpperCase()}({agg.column})
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5. Drop Nulls Step Changes */}
      {stepType === "drop_nulls" && Boolean(details.columns) && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-medium text-slate-600 block">
            Nulls Dropped on Columns:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {((details.columns as string[]) || []).map((col, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 bg-white border border-rose-200 px-2 py-1 rounded text-xs font-mono text-rose-800 shadow-2xs"
              >
                <Trash2 className="w-3 h-3 text-rose-500" /> {col} IS NOT NULL
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 6. Select Columns Step Changes */}
      {stepType === "select_columns" && Boolean(details.columns) && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-medium text-slate-600 block">
            Projected Columns ({((details.columns as string[]) || []).length}):
          </span>
          <div className="flex flex-wrap gap-1.5">
            {((details.columns as string[]) || []).map((col, i) => (
              <span
                key={i}
                className="bg-white border border-teal-200 px-2 py-0.5 rounded text-xs font-mono text-teal-800 shadow-2xs"
              >
                {col}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 7. Dedupe Step Changes */}
      {stepType === "dedupe" && (
        <div className="flex items-center gap-2 text-xs text-indigo-900 bg-white border border-indigo-200 px-3 py-1.5 rounded-md shadow-2xs">
          <CopyX className="w-3.5 h-3.5 text-indigo-600" />
          <span>
            Deduplicated on:{" "}
            <strong className="font-mono">
              {details.columns ? ((details.columns as string[]) || []).join(", ") : "All Columns (DISTINCT)"}
            </strong>
          </span>
        </div>
      )}

      {/* 7b. Cast Step Changes */}
      {stepType === "cast" && Boolean(details.mapping) && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-medium text-slate-600 block">
            Changed Data Types:
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            {Object.entries((details.mapping as Record<string, string>) || {}).map(([col, typ], i) => (
              <div
                key={i}
                className="flex items-center justify-between bg-white border border-violet-200 rounded-md px-2.5 py-1 text-xs shadow-2xs"
              >
                <span className="font-mono font-medium text-slate-700">{col}</span>
                <span className="px-1.5 py-0.5 bg-violet-100 text-violet-800 text-[10px] font-bold rounded uppercase">
                  {typ}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 7c. Text Clean Step Changes */}
      {stepType === "text_clean" && Boolean(details.operations) && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-medium text-slate-600 block">
            Text Cleanups Applied:
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            {Object.entries((details.operations as Record<string, string>) || {}).map(([col, op], i) => (
              <div
                key={i}
                className="flex items-center justify-between bg-white border border-sky-200 rounded-md px-2.5 py-1 text-xs shadow-2xs"
              >
                <span className="font-mono font-medium text-slate-700">{col}</span>
                <span className="px-1.5 py-0.5 bg-sky-100 text-sky-800 text-[10px] font-bold rounded uppercase">
                  {op}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 7b. Union Step Changes */}
      {stepType === "union" && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-medium text-slate-600 block">
            Union / Stack Datasets (
            <strong>{details.distinct ? "UNION (Deduplicated)" : "UNION ALL (All Rows)"}</strong>):
          </span>
          <div className="flex flex-wrap gap-2">
            {((details.inputs as string[]) || []).map((inp, idx) => (
              <div
                key={idx}
                className="flex items-center gap-1.5 bg-white border border-fuchsia-200 rounded-md px-2.5 py-1 text-xs shadow-2xs"
              >
                <span className="w-2 h-2 rounded-full bg-fuchsia-500" />
                <span className="font-mono font-medium text-slate-700">{inp}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 8. Source Node */}
      {stepType === "source" && (
        <div className="flex items-center gap-2 text-xs text-blue-900 bg-white border border-blue-200 px-3 py-1.5 rounded-md shadow-2xs">
          <Database className="w-3.5 h-3.5 text-blue-600" />
          <span>
            Source Database Table: <strong className="font-mono">{node.label}</strong> (Raw Table Ingestion)
          </span>
        </div>
      )}

      {/* 9. Output Node */}
      {stepType === "output" && (
        <div className="flex items-center gap-2 text-xs text-orange-900 bg-white border border-orange-200 px-3 py-1.5 rounded-md shadow-2xs">
          <CheckCircle2 className="w-3.5 h-3.5 text-orange-600" />
          <span>
            Final Transformed Dataset ready for Tableau Hyper Extract publishing.
          </span>
        </div>
      )}
    </div>
  );
}

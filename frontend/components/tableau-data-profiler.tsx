"use client";

import React, { useMemo } from "react";
import {
  Hash,
  Type,
  Calendar,
  Layers,
  ChevronDown,
} from "lucide-react";

interface ColumnMetric {
  name: string;
  dataType: string;
  totalCount: number;
  distinctCount: number;
  nullCount: number;
  frequencies: { value: string; count: number; percent: number }[];
}

export function TableauDataProfiler({
  title,
  rows,
}: {
  title: string;
  rows: Record<string, unknown>[] | null;
}) {
  const metrics: ColumnMetric[] = useMemo(() => {
    if (!rows || rows.length === 0) return [];
    const keys = Object.keys(rows[0]);
    const total = rows.length;

    return keys.map((col) => {
      const counts: Record<string, number> = {};
      let nulls = 0;
      let inferredType = "string";

      rows.forEach((r) => {
        const val = r[col];
        if (val === null || val === undefined || val === "") {
          nulls++;
        } else {
          const strVal = String(val);
          counts[strVal] = (counts[strVal] || 0) + 1;
          if (typeof val === "number") inferredType = "number";
          else if (!isNaN(Date.parse(strVal)) && strVal.includes("-")) inferredType = "date";
        }
      });

      const distinct = Object.keys(counts).length;
      const sortedFreqs = Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([val, count]) => ({
          value: val,
          count,
          percent: Math.round((count / total) * 100),
        }));

      return {
        name: col,
        dataType: inferredType,
        totalCount: total,
        distinctCount: distinct,
        nullCount: nulls,
        frequencies: sortedFreqs,
      };
    });
  }, [rows]);

  if (!rows || rows.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-slate-400 border border-dashed border-slate-200 rounded-lg">
        Select a node on the canvas to inspect its live data profile and sample records.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-slate-200 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
            {title}
          </span>
          <span className="text-[11px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
            {rows.length} rows previewed · {metrics.length} fields
          </span>
        </div>
      </div>

      {/* Field Profile Cards Scroll Container (Tableau Prep Profile Pane) */}
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin">
        {metrics.map((m) => (
          <div
            key={m.name}
            className="w-56 shrink-0 bg-white border border-slate-200 rounded-lg shadow-xs hover:border-blue-400 transition-all p-2.5 flex flex-col justify-between text-xs"
          >
            {/* Card Header */}
            <div>
              <div className="flex items-center justify-between text-slate-400 mb-1">
                <span className="flex items-center gap-1 font-mono text-[10px] text-blue-600 font-semibold uppercase">
                  {m.dataType === "number" ? <Hash className="w-3 h-3" /> : m.dataType === "date" ? <Calendar className="w-3 h-3" /> : <Type className="w-3 h-3" />}
                  {m.dataType}
                </span>
                <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                  <Layers className="w-3 h-3" /> {m.distinctCount} unique
                </span>
              </div>
              <h4 className="font-semibold text-slate-800 truncate text-xs" title={m.name}>
                {m.name}
              </h4>
            </div>

            {/* Distribution Mini-Bars / Histograms */}
            <div className="my-2 space-y-1">
              {m.frequencies.map((freq, idx) => (
                <div key={idx} className="space-y-0.5">
                  <div className="flex justify-between text-[10px] text-slate-600">
                    <span className="truncate max-w-[120px]" title={freq.value}>
                      {freq.value}
                    </span>
                    <span className="text-slate-400 font-mono">{freq.percent}%</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
                      style={{ width: `${freq.percent}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Card Footer */}
            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-400">
              <span>Nulls: {m.nullCount}</span>
              <span className="text-blue-600 cursor-pointer hover:underline flex items-center">
                Clean <ChevronDown className="w-2.5 h-2.5 ml-0.5" />
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

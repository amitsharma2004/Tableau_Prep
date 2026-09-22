"use client";

import React, { useState } from "react";
import { GitMerge, X, ArrowRight, Check } from "lucide-react";

export interface JoinConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  leftTable: string;
  rightTable: string;
  leftColumns: string[];
  rightColumns: string[];
  onConfirm: (config: {
    joinType: "inner" | "left" | "right" | "full";
    leftCol: string;
    rightCol: string;
    outputAlias: string;
  }) => void;
}

export function JoinConfigModal({
  isOpen,
  onClose,
  leftTable,
  rightTable,
  leftColumns,
  rightColumns,
  onConfirm,
}: JoinConfigModalProps) {
  const [joinType, setJoinType] = useState<"inner" | "left" | "right" | "full">("inner");

  // Auto-detect best matching column or fallback
  const detectedLeft =
    leftColumns.find((c) => rightColumns.includes(c)) ||
    leftColumns.find((c) => c.endsWith("_id")) ||
    leftColumns[0] ||
    "";
  const detectedRight =
    rightColumns.find((c) => c === detectedLeft) ||
    rightColumns.find((c) => c.endsWith("_id")) ||
    rightColumns[0] ||
    "";

  const [leftCol, setLeftCol] = useState<string>(detectedLeft);
  const [rightCol, setRightCol] = useState<string>(detectedRight);
  const [outputAlias, setOutputAlias] = useState<string>(
    `${leftTable.toLowerCase()}_${rightTable.toLowerCase()}_joined`
  );

  // Sync state if props change
  React.useEffect(() => {
    const dLeft =
      leftColumns.find((c) => rightColumns.includes(c)) ||
      leftColumns.find((c) => c.endsWith("_id")) ||
      leftColumns[0] ||
      "";
    const dRight =
      rightColumns.find((c) => c === dLeft) ||
      rightColumns.find((c) => c.endsWith("_id")) ||
      rightColumns[0] ||
      "";
    setLeftCol(dLeft);
    setRightCol(dRight);
    setOutputAlias(`${leftTable.toLowerCase()}_${rightTable.toLowerCase()}_joined`);
  }, [leftTable, rightTable, leftColumns, rightColumns]);

  if (!isOpen) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!leftCol || !rightCol) return;
    onConfirm({
      joinType,
      leftCol,
      rightCol,
      outputAlias: outputAlias.trim() || `${leftTable}_${rightTable}_joined`,
    });
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="p-1.5 bg-emerald-100 text-emerald-700 rounded-lg">
              <GitMerge className="w-4 h-4" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-800">Configure Table Join</h3>
              <p className="text-[11px] text-slate-500">Connect and combine records like in Tableau Prep</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-xs">
          {/* Join Type Selector */}
          <div>
            <label className="font-semibold text-slate-700 block mb-1.5">Join Type</label>
            <div className="grid grid-cols-4 gap-2">
              {[
                { type: "inner", label: "Inner", desc: "Matching only" },
                { type: "left", label: "Left", desc: "All from left" },
                { type: "right", label: "Right", desc: "All from right" },
                { type: "full", label: "Full Outer", desc: "All records" },
              ].map((item) => (
                <button
                  type="button"
                  key={item.type}
                  onClick={() => setJoinType(item.type as any)}
                  className={`p-2 rounded-lg border text-center transition-all cursor-pointer ${
                    joinType === item.type
                      ? "border-emerald-500 bg-emerald-50/60 text-emerald-900 ring-2 ring-emerald-200 font-bold"
                      : "border-slate-200 hover:border-slate-300 text-slate-600 bg-white"
                  }`}
                >
                  <div className="text-xs uppercase tracking-wide">{item.label}</div>
                  <div className="text-[9px] text-slate-400 font-normal mt-0.5">{item.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Join Condition Clause */}
          <div className="bg-slate-50/80 border border-slate-200 rounded-lg p-3.5 space-y-3">
            <span className="font-semibold text-slate-700 block">Join Condition (ON clause)</span>

            <div className="grid grid-cols-5 items-center gap-2">
              {/* Left Column Selector */}
              <div className="col-span-2">
                <label className="text-[10px] text-slate-500 font-mono block mb-1 truncate" title={leftTable}>
                  {leftTable}
                </label>
                <select
                  value={leftCol}
                  onChange={(e) => setLeftCol(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded px-2 py-1.5 text-xs text-slate-800 font-mono focus:outline-none focus:border-emerald-500"
                >
                  {leftColumns.map((col) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </select>
              </div>

              {/* Equals */}
              <div className="col-span-1 text-center font-bold text-slate-400 text-sm">
                =
              </div>

              {/* Right Column Selector */}
              <div className="col-span-2">
                <label className="text-[10px] text-slate-500 font-mono block mb-1 truncate" title={rightTable}>
                  {rightTable}
                </label>
                <select
                  value={rightCol}
                  onChange={(e) => setRightCol(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded px-2 py-1.5 text-xs text-slate-800 font-mono focus:outline-none focus:border-emerald-500"
                >
                  {rightColumns.map((col) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Output Alias */}
          <div>
            <label className="font-semibold text-slate-700 block mb-1">Resulting Node / Step Name</label>
            <input
              type="text"
              value={outputAlias}
              onChange={(e) => setOutputAlias(e.target.value)}
              placeholder="e.g. customers_orders_joined"
              className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-800 focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!leftCol || !rightCol}
              className="px-4 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-all shadow-sm flex items-center gap-1.5 disabled:opacity-40 cursor-pointer"
            >
              <Check className="w-3.5 h-3.5" />
              Apply Join Step
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

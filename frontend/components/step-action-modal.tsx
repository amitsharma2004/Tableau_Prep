"use client";

import React, { useState } from "react";
import {
  Tag,
  Filter,
  Columns,
  Trash2,
  CopyX,
  X,
  Check,
  Plus,
  Trash,
  Binary,
  Type,
} from "lucide-react";

export interface StepActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourceAlias: string;
  columns: string[];
  onApplyStep: (step: any) => void;
}

type TabType =
  | "rename"
  | "select_columns"
  | "filter"
  | "drop_nulls"
  | "dedupe"
  | "cast"
  | "text_clean";

export function StepActionModal({
  isOpen,
  onClose,
  sourceAlias,
  columns,
  onApplyStep,
}: StepActionModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>("rename");

  // State for Rename
  const [renamePairs, setRenamePairs] = useState<{ oldCol: string; newCol: string }[]>([
    { oldCol: columns[0] || "", newCol: "" },
  ]);

  // State for Select/Remove Columns
  const [selectedCols, setSelectedCols] = useState<string[]>(columns);

  // State for Filter
  const [filterConditions, setFilterConditions] = useState<
    { column: string; operator: string; value: string }[]
  >([{ column: columns[0] || "", operator: "=", value: "" }]);
  const [filterLogic, setFilterLogic] = useState<"and" | "or">("and");

  // State for Drop Nulls
  const [nullDropCols, setNullDropCols] = useState<string[]>([]);

  // State for Dedupe
  const [dedupeCols, setDedupeCols] = useState<string[]>([]);

  // State for Change Data Type (Cast)
  const [castPairs, setCastPairs] = useState<
    { column: string; targetType: "string" | "integer" | "float" | "date" | "boolean" }[]
  >([{ column: columns[0] || "", targetType: "string" }]);

  // State for Text Cleanup
  const [textCleanPairs, setTextCleanPairs] = useState<
    { column: string; operation: "trim" | "upper" | "lower" }[]
  >([{ column: columns[0] || "", operation: "trim" }]);

  // Output alias
  const [outputAlias, setOutputAlias] = useState<string>(`${sourceAlias}_cleaned`);

  // Sync when columns or sourceAlias change
  React.useEffect(() => {
    setSelectedCols(columns);
    setRenamePairs([{ oldCol: columns[0] || "", newCol: "" }]);
    setFilterConditions([{ column: columns[0] || "", operator: "=", value: "" }]);
    setCastPairs([{ column: columns[0] || "", targetType: "string" }]);
    setTextCleanPairs([{ column: columns[0] || "", operation: "trim" }]);
    setOutputAlias(`${sourceAlias}_cleaned`);
  }, [sourceAlias, columns]);

  if (!isOpen) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const finalAlias = outputAlias.trim() || `${sourceAlias}_cleaned`;

    if (activeTab === "rename") {
      const mapping: Record<string, string> = {};
      renamePairs.forEach((p) => {
        if (p.oldCol && p.newCol.trim()) {
          mapping[p.oldCol] = p.newCol.trim();
        }
      });
      if (Object.keys(mapping).length === 0) return;
      onApplyStep({
        type: "rename",
        target: sourceAlias,
        output_alias: finalAlias,
        mapping,
      });
    } else if (activeTab === "select_columns") {
      if (selectedCols.length === 0) return;
      onApplyStep({
        type: "select_columns",
        target: sourceAlias,
        output_alias: finalAlias,
        columns: selectedCols,
      });
    } else if (activeTab === "filter") {
      const validConditions = filterConditions.filter((c) => c.column);
      if (validConditions.length === 0) return;
      onApplyStep({
        type: "filter",
        target: sourceAlias,
        output_alias: finalAlias,
        conditions: validConditions.map((c) => ({
          column: c.column,
          operator: c.operator,
          value: isNaN(Number(c.value)) ? c.value : Number(c.value),
        })),
        logic: filterLogic,
      });
    } else if (activeTab === "drop_nulls") {
      if (nullDropCols.length === 0) return;
      onApplyStep({
        type: "drop_nulls",
        target: sourceAlias,
        output_alias: finalAlias,
        columns: nullDropCols,
      });
    } else if (activeTab === "dedupe") {
      onApplyStep({
        type: "dedupe",
        target: sourceAlias,
        output_alias: finalAlias,
        columns: dedupeCols.length > 0 ? dedupeCols : null,
      });
    } else if (activeTab === "cast") {
      const mapping: Record<string, string> = {};
      castPairs.forEach((p) => {
        if (p.column) {
          mapping[p.column] = p.targetType;
        }
      });
      if (Object.keys(mapping).length === 0) return;
      onApplyStep({
        type: "cast",
        target: sourceAlias,
        output_alias: finalAlias,
        mapping,
      });
    } else if (activeTab === "text_clean") {
      const operations: Record<string, string> = {};
      textCleanPairs.forEach((p) => {
        if (p.column) {
          operations[p.column] = p.operation;
        }
      });
      if (Object.keys(operations).length === 0) return;
      onApplyStep({
        type: "text_clean",
        target: sourceAlias,
        output_alias: finalAlias,
        operations,
      });
    }

    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-2xl overflow-hidden flex flex-col max-h-[88vh]">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50/80 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span>Insert Transformation Step</span>
              <span className="text-[11px] px-2 py-0.5 bg-blue-100 text-blue-700 font-mono rounded">
                on {sourceAlias}
              </span>
            </h3>
            <p className="text-[11px] text-slate-500">
              Transform, clean, filter, typecast, or rename fields like in Tableau Prep Builder
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 bg-slate-50 px-4 gap-1 pt-2 overflow-x-auto">
          {[
            { id: "rename", label: "Rename Field", icon: Tag },
            { id: "cast", label: "Change Type", icon: Binary },
            { id: "text_clean", label: "Text Cleanup", icon: Type },
            { id: "select_columns", label: "Keep / Remove", icon: Columns },
            { id: "filter", label: "Filter Values", icon: Filter },
            { id: "drop_nulls", label: "Drop Nulls", icon: Trash2 },
            { id: "dedupe", label: "Deduplicate", icon: CopyX },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 whitespace-nowrap transition-all cursor-pointer ${
                  isActive
                    ? "border-blue-600 text-blue-600 bg-white rounded-t-lg shadow-2xs"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
          {/* TAB 1: RENAME */}
          {activeTab === "rename" && (
            <div className="space-y-3">
              <span className="text-slate-600 font-medium block">
                Choose existing columns and assign their new alias:
              </span>
              {renamePairs.map((pair, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <select
                    value={pair.oldCol}
                    onChange={(e) => {
                      const updated = [...renamePairs];
                      updated[idx].oldCol = e.target.value;
                      setRenamePairs(updated);
                    }}
                    className="flex-1 bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-mono text-xs focus:outline-none focus:border-blue-500"
                  >
                    {columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <span className="text-slate-400 font-semibold">➔</span>
                  <input
                    type="text"
                    value={pair.newCol}
                    onChange={(e) => {
                      const updated = [...renamePairs];
                      updated[idx].newCol = e.target.value;
                      setRenamePairs(updated);
                    }}
                    placeholder="new_column_name"
                    className="flex-1 bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-mono text-xs focus:outline-none focus:border-blue-500"
                  />
                  {renamePairs.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setRenamePairs(renamePairs.filter((_, i) => i !== idx))}
                      className="p-1.5 text-slate-400 hover:text-red-500 rounded hover:bg-red-50 cursor-pointer"
                    >
                      <Trash className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={() => setRenamePairs([...renamePairs, { oldCol: columns[0] || "", newCol: "" }])}
                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-semibold cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" /> Add another column rename
              </button>
            </div>
          )}

          {/* TAB 2: CHANGE DATA TYPE (CAST) */}
          {activeTab === "cast" && (
            <div className="space-y-3">
              <span className="text-slate-600 font-medium block">
                Cast column data types (e.g. string to integer, number to date):
              </span>
              {castPairs.map((pair, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <select
                    value={pair.column}
                    onChange={(e) => {
                      const updated = [...castPairs];
                      updated[idx].column = e.target.value;
                      setCastPairs(updated);
                    }}
                    className="flex-1 bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-mono text-xs focus:outline-none focus:border-blue-500"
                  >
                    {columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <span className="text-slate-400 font-semibold">AS</span>
                  <select
                    value={pair.targetType}
                    onChange={(e) => {
                      const updated = [...castPairs];
                      updated[idx].targetType = e.target.value as any;
                      setCastPairs(updated);
                    }}
                    className="flex-1 bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-semibold text-xs text-violet-700 focus:outline-none focus:border-blue-500 uppercase"
                  >
                    <option value="string">String (Text)</option>
                    <option value="integer">Integer (Whole Number)</option>
                    <option value="float">Float (Decimal)</option>
                    <option value="date">Date</option>
                    <option value="boolean">Boolean (True/False)</option>
                  </select>
                  {castPairs.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setCastPairs(castPairs.filter((_, i) => i !== idx))}
                      className="p-1.5 text-slate-400 hover:text-red-500 rounded hover:bg-red-50 cursor-pointer"
                    >
                      <Trash className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={() => setCastPairs([...castPairs, { column: columns[0] || "", targetType: "string" }])}
                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-semibold cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" /> Add another type cast
              </button>
            </div>
          )}

          {/* TAB 3: TEXT CLEANUP */}
          {activeTab === "text_clean" && (
            <div className="space-y-3">
              <span className="text-slate-600 font-medium block">
                Standardize and clean text fields (trim extra whitespace, change case):
              </span>
              {textCleanPairs.map((pair, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <select
                    value={pair.column}
                    onChange={(e) => {
                      const updated = [...textCleanPairs];
                      updated[idx].column = e.target.value;
                      setTextCleanPairs(updated);
                    }}
                    className="flex-1 bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-mono text-xs focus:outline-none focus:border-blue-500"
                  >
                    {columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <select
                    value={pair.operation}
                    onChange={(e) => {
                      const updated = [...textCleanPairs];
                      updated[idx].operation = e.target.value as any;
                      setTextCleanPairs(updated);
                    }}
                    className="flex-1 bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-semibold text-xs text-sky-700 focus:outline-none focus:border-blue-500"
                  >
                    <option value="trim">Trim Whitespace (TRIM)</option>
                    <option value="upper">UPPERCASE (UPPER)</option>
                    <option value="lower">lowercase (LOWER)</option>
                  </select>
                  {textCleanPairs.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setTextCleanPairs(textCleanPairs.filter((_, i) => i !== idx))}
                      className="p-1.5 text-slate-400 hover:text-red-500 rounded hover:bg-red-50 cursor-pointer"
                    >
                      <Trash className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={() => setTextCleanPairs([...textCleanPairs, { column: columns[0] || "", operation: "trim" }])}
                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-semibold cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" /> Add another text cleanup
              </button>
            </div>
          )}

          {/* TAB 4: SELECT / REMOVE COLUMNS */}
          {activeTab === "select_columns" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-600 font-medium">
                  Check columns to KEEP in the dataset ({selectedCols.length}/{columns.length}):
                </span>
                <div className="space-x-2">
                  <button
                    type="button"
                    onClick={() => setSelectedCols(columns)}
                    className="text-[11px] text-blue-600 hover:underline cursor-pointer"
                  >
                    Select All
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedCols([])}
                    className="text-[11px] text-slate-400 hover:underline cursor-pointer"
                  >
                    Clear
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-48 overflow-y-auto p-2 border border-slate-200 rounded-lg bg-slate-50/50">
                {columns.map((col) => {
                  const isChecked = selectedCols.includes(col);
                  return (
                    <label
                      key={col}
                      className={`flex items-center gap-2 p-2 rounded-md border text-xs cursor-pointer select-none transition-colors ${
                        isChecked
                          ? "bg-blue-50/80 border-blue-300 text-blue-900 font-medium"
                          : "bg-white border-slate-200 text-slate-500 line-through"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedCols([...selectedCols, col]);
                          } else {
                            setSelectedCols(selectedCols.filter((c) => c !== col));
                          }
                        }}
                        className="rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span className="truncate font-mono">{col}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 5: FILTER */}
          {activeTab === "filter" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-slate-600 font-medium">Filter rules:</span>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-500">Condition logic:</span>
                  <select
                    value={filterLogic}
                    onChange={(e) => setFilterLogic(e.target.value as "and" | "or")}
                    className="bg-white border border-slate-300 rounded px-2 py-0.5 text-xs font-semibold"
                  >
                    <option value="and">AND</option>
                    <option value="or">OR</option>
                  </select>
                </div>
              </div>
              {filterConditions.map((cond, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <select
                    value={cond.column}
                    onChange={(e) => {
                      const updated = [...filterConditions];
                      updated[idx].column = e.target.value;
                      setFilterConditions(updated);
                    }}
                    className="flex-1 bg-white border border-slate-300 rounded-lg px-2 py-1.5 font-mono text-xs focus:outline-none focus:border-blue-500"
                  >
                    {columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <select
                    value={cond.operator}
                    onChange={(e) => {
                      const updated = [...filterConditions];
                      updated[idx].operator = e.target.value;
                      setFilterConditions(updated);
                    }}
                    className="w-24 bg-white border border-slate-300 rounded-lg px-2 py-1.5 text-xs font-mono font-semibold"
                  >
                    <option value="=">=</option>
                    <option value="!=">!=</option>
                    <option value=">">&gt;</option>
                    <option value="<">&lt;</option>
                    <option value=">=">&gt;=</option>
                    <option value="<=">&lt;=</option>
                    <option value="is_null">IS NULL</option>
                    <option value="is_not_null">NOT NULL</option>
                  </select>
                  {!["is_null", "is_not_null"].includes(cond.operator) && (
                    <input
                      type="text"
                      value={cond.value}
                      onChange={(e) => {
                        const updated = [...filterConditions];
                        updated[idx].value = e.target.value;
                        setFilterConditions(updated);
                      }}
                      placeholder="Value"
                      className="flex-1 bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-mono focus:outline-none focus:border-blue-500"
                    />
                  )}
                  {filterConditions.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setFilterConditions(filterConditions.filter((_, i) => i !== idx))}
                      className="p-1.5 text-slate-400 hover:text-red-500 rounded hover:bg-red-50 cursor-pointer"
                    >
                      <Trash className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setFilterConditions([
                    ...filterConditions,
                    { column: columns[0] || "", operator: "=", value: "" },
                  ])
                }
                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-semibold cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" /> Add condition
              </button>
            </div>
          )}

          {/* TAB 6: DROP NULLS */}
          {activeTab === "drop_nulls" && (
            <div className="space-y-2">
              <span className="text-slate-600 font-medium block">
                Select columns that must NOT contain NULL values (rows with nulls will be dropped):
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-48 overflow-y-auto p-2 border border-slate-200 rounded-lg bg-slate-50/50">
                {columns.map((col) => {
                  const isChecked = nullDropCols.includes(col);
                  return (
                    <label
                      key={col}
                      className={`flex items-center gap-2 p-2 rounded-md border text-xs cursor-pointer select-none transition-colors ${
                        isChecked
                          ? "bg-rose-50/80 border-rose-300 text-rose-900 font-medium"
                          : "bg-white border-slate-200 text-slate-600"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setNullDropCols([...nullDropCols, col]);
                          } else {
                            setNullDropCols(nullDropCols.filter((c) => c !== col));
                          }
                        }}
                        className="rounded text-rose-600 focus:ring-rose-500"
                      />
                      <span className="truncate font-mono">{col}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 7: DEDUPE */}
          {activeTab === "dedupe" && (
            <div className="space-y-2">
              <span className="text-slate-600 font-medium block">
                Select columns to identify duplicates (leave empty to deduplicate on ALL columns):
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-48 overflow-y-auto p-2 border border-slate-200 rounded-lg bg-slate-50/50">
                {columns.map((col) => {
                  const isChecked = dedupeCols.includes(col);
                  return (
                    <label
                      key={col}
                      className={`flex items-center gap-2 p-2 rounded-md border text-xs cursor-pointer select-none transition-colors ${
                        isChecked
                          ? "bg-indigo-50/80 border-indigo-300 text-indigo-900 font-medium"
                          : "bg-white border-slate-200 text-slate-600"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setDedupeCols([...dedupeCols, col]);
                          } else {
                            setDedupeCols(dedupeCols.filter((c) => c !== col));
                          }
                        }}
                        className="rounded text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="truncate font-mono">{col}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Resulting Node Name */}
          <div className="pt-2 border-t border-slate-100">
            <label className="font-semibold text-slate-700 block mb-1">Resulting Node / Step Name</label>
            <input
              type="text"
              value={outputAlias}
              onChange={(e) => setOutputAlias(e.target.value)}
              placeholder="e.g. customers_filtered"
              className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-800 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Actions */}
          <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
            >
              <Check className="w-3.5 h-3.5" />
              Apply Step to Flow
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

import type { PlanDraft, PlanStep } from "@/lib/types";

function describeStep(step: PlanStep): string {
  switch (step.type) {
    case "join":
      return `Join "${step.left}" and "${step.right}" (${step.join_type}) on ${step.on
        .map(([l, r]) => `${l} = ${r}`)
        .join(", ")} → "${step.output_alias}"`;
    case "filter":
      return `Filter "${step.target}" where ${step.conditions
        .map((c) => `${c.column} ${c.operator}${c.value !== undefined && c.value !== null ? ` ${JSON.stringify(c.value)}` : ""}`)
        .join(` ${step.logic.toUpperCase()} `)} → "${step.output_alias}"`;
    case "drop_nulls":
      return `Drop rows from "${step.target}" where any of [${step.columns.join(", ")}] is null → "${step.output_alias}"`;
    case "dedupe":
      return `De-duplicate "${step.target}"${step.columns ? ` on [${step.columns.join(", ")}]` : ""} → "${step.output_alias}"`;
    case "rename":
      return `Rename columns on "${step.target}" (${Object.entries(step.mapping)
        .map(([o, n]) => `${o} → ${n}`)
        .join(", ")}) → "${step.output_alias}"`;
    case "select_columns":
      return `Select [${step.columns.join(", ")}] from "${step.target}" → "${step.output_alias}"`;
    case "aggregate":
      return `Group "${step.target}" by [${step.group_by.join(", ")}], compute ${step.aggregations
        .map((a) => `${a.function}(${a.column}) as ${a.alias}`)
        .join(", ")} → "${step.output_alias}"`;
    default:
      return JSON.stringify(step);
  }
}

export function PlanSummary({ plan }: { plan: PlanDraft }) {
  return (
    <div className="space-y-4">
      <p className="text-slate-800">{plan.summary}</p>

      <div>
        <h3 className="text-sm font-medium text-slate-600 mb-1">Sources</h3>
        <ul className="text-sm text-slate-800 space-y-0.5">
          {plan.sources.map((s) => (
            <li key={s.alias}>
              <code className="bg-slate-100 px-1 rounded">{s.alias}</code> = {s.schema_name}.{s.table_name}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-600 mb-1">Steps</h3>
        <ol className="text-sm text-slate-800 space-y-1 list-decimal list-inside">
          {plan.steps.map((step, i) => (
            <li key={i}>{describeStep(step)}</li>
          ))}
        </ol>
      </div>

      <p className="text-sm text-slate-500">
        Output: <code className="bg-slate-100 px-1 rounded">{plan.output_alias}</code>
      </p>
    </div>
  );
}

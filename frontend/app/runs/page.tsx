"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api-client";
import { useActor } from "@/lib/actor-context";
import type { Run } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

export default function RunsPage() {
  const { actorEmail } = useActor();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRuns(actorEmail)
      .then(setRuns)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load runs"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Run history</h1>
        <p className="text-slate-600 mt-1">Audit trail of every preview and execute run across all flows.</p>
      </div>

      {error && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}

      {loading ? (
        <p className="text-slate-500 text-sm">Loading...</p>
      ) : runs.length === 0 ? (
        <p className="text-slate-500 text-sm">No runs yet.</p>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left font-medium text-slate-600 px-4 py-2">Type</th>
                <th className="text-left font-medium text-slate-600 px-4 py-2">Trigger</th>
                <th className="text-left font-medium text-slate-600 px-4 py-2">Status</th>
                <th className="text-left font-medium text-slate-600 px-4 py-2">Rows</th>
                <th className="text-left font-medium text-slate-600 px-4 py-2">Publish</th>
                <th className="text-left font-medium text-slate-600 px-4 py-2">Started</th>
                <th className="text-left font-medium text-slate-600 px-4 py-2">By</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="px-4 py-2 font-mono text-xs">{run.run_type}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
                        run.trigger_type === "scheduled"
                          ? "bg-purple-100 text-purple-800"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {run.trigger_type === "scheduled" ? "⏰ Scheduled" : "👤 Manual"}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={run.status} />
                    {run.row_count_anomaly && <span className="ml-1 text-amber-600 text-xs">⚠ anomaly</span>}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {run.rows_before ?? "-"} → {run.rows_after ?? "-"}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{run.publish_status ?? "-"}</td>
                  <td className="px-4 py-2 text-slate-600">{new Date(run.started_at).toLocaleString()}</td>
                  <td className="px-4 py-2 text-slate-600">{run.triggered_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-sm text-slate-500">
        <Link href="/flows" className="text-blue-600 underline">
          Back to flows
        </Link>
      </p>
    </div>
  );
}

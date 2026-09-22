"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api-client";
import { useActor } from "@/lib/actor-context";
import type { Flow } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

export default function FlowsPage() {
  const { actorEmail } = useActor();
  const [flows, setFlows] = useState<Flow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listFlows(actorEmail)
      .then(setFlows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load flows"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Flows</h1>
          <p className="text-slate-600 mt-1">Each flow is one natural-language request through to a published Tableau datasource.</p>
        </div>
        <Link href="/flows/new" className="btn-primary">
          New flow
        </Link>
      </div>

      {error && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}

      {loading ? (
        <p className="text-slate-500 text-sm">Loading...</p>
      ) : flows.length === 0 ? (
        <p className="text-slate-500 text-sm">No flows yet. Create one to get started.</p>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-100">
          {flows.map((flow) => (
            <Link
              key={flow.id}
              href={`/flows/${flow.id}`}
              className="p-4 flex items-center justify-between gap-4 hover:bg-slate-50 block"
            >
              <div>
                <p className="font-medium text-slate-900">{flow.name}</p>
                <p className="text-sm text-slate-500 line-clamp-1">{flow.nl_request}</p>
              </div>
              <StatusBadge status={flow.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

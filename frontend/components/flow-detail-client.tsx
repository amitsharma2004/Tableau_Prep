"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import { useActor } from "@/lib/actor-context";
import type { Flow, FlowSchedule, PlanVersion, Run } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";
import { DataTable } from "@/components/data-table";
import { ScheduleCard } from "@/components/schedule-card";
import { VisualFlowCanvas } from "@/components/visual-flow-canvas";
import type { PrepNodeData } from "@/lib/plan-to-graph";

export function FlowDetailClient({ flowId }: { flowId: string }) {
  const { actorEmail } = useActor();
  const [flow, setFlow] = useState<Flow | null>(null);
  const [planVersion, setPlanVersion] = useState<PlanVersion | null>(null);
  const [latestPreviewRun, setLatestPreviewRun] = useState<Run | null>(null);
  const [latestExecuteRun, setLatestExecuteRun] = useState<Run | null>(null);
  const [schedule, setSchedule] = useState<FlowSchedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [acknowledgeAnomaly, setAcknowledgeAnomaly] = useState(false);
  const [selectedNode, setSelectedNode] = useState<PrepNodeData | null>(null);

  async function loadAll() {
    setError(null);
    try {
      const f = await api.getFlow(actorEmail, flowId);
      setFlow(f);

      if (f.active_plan_version_id) {
        try {
          setPlanVersion(await api.getActivePlan(actorEmail, flowId));
        } catch {
          setPlanVersion(null);
        }
      } else {
        setPlanVersion(null);
      }

      try {
        setSchedule(await api.getSchedule(actorEmail, flowId));
      } catch {
        setSchedule(null);
      }

      const runs = await api.listRuns(actorEmail, flowId);
      setLatestPreviewRun(runs.find((r) => r.run_type === "preview") ?? null);
      setLatestExecuteRun(runs.find((r) => r.run_type === "execute") ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load flow");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Fetch-on-mount/flowId-change against an external REST API, not a
    // reaction to local render state - the intentional exception here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flowId]);

  async function runAction(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await loadAll();
      setEditing(false);
      setAcknowledgeAnomaly(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="text-slate-500 text-sm">Loading...</p>;
  if (!flow) return <p className="text-red-700 text-sm">Flow not found.</p>;

  const status = flow.status;

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">{flow.name}</h1>
          <StatusBadge status={status} />
        </div>
        <p className="text-slate-600 mt-1">{flow.nl_request}</p>
      </div>

      {error && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}

      {/* Step 1: no plan yet */}
      {status === "draft" && (
        <Panel title="Step 1 · Generate a plan">
          <p className="text-sm text-slate-600 mb-3">Claude will propose a transformation plan from your request above.</p>
          <button disabled={busy} onClick={() => runAction(() => api.generatePlan(actorEmail, flowId))} className="btn-primary">
            {busy ? "Generating..." : "Generate plan"}
          </button>
        </Panel>
      )}

      {/* Failed - recovery options */}
      {status === "failed" && (
        <Panel title="Run failed">
          <p className="text-sm text-red-700 mb-3">
            {latestExecuteRun?.error_message ?? "The last execute run failed. See details below."}
          </p>
          <div className="flex gap-2">
            <button disabled={busy} onClick={() => runAction(() => api.generatePlan(actorEmail, flowId))} className="btn-secondary">
              Regenerate plan
            </button>
            <button disabled={busy} onClick={() => runAction(() => api.runPreview(actorEmail, flowId))} className="btn-secondary">
              Retry preview (same plan)
            </button>
          </div>
        </Panel>
      )}

      {/* Visual Tableau Prep Flow Canvas */}
      {planVersion && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Visual Transformation Flow (v{planVersion.version_number})
              </h2>
              <p className="text-xs text-slate-500">
                Interactive node graph. Click any node to inspect parameters and preview data flow.
              </p>
            </div>
            {status === "plan_pending_approval" && (
              <div className="flex items-center gap-2">
                <button
                  disabled={busy}
                  onClick={() => runAction(() => api.approvePlan(actorEmail, flowId))}
                  className="px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded shadow-sm cursor-pointer"
                >
                  Approve Plan
                </button>
                <button
                  disabled={busy}
                  onClick={() => {
                    setEditText(JSON.stringify(planVersion.plan, null, 2));
                    setEditing(!editing);
                  }}
                  className="px-3 py-1.5 text-xs font-medium bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded cursor-pointer"
                >
                  {editing ? "Close JSON" : "Raw JSON"}
                </button>
              </div>
            )}
          </div>

          <VisualFlowCanvas
            plan={planVersion.plan}
            onNodeSelect={(node) => setSelectedNode(node)}
          />

          {/* Node Inspector Drawer */}
          {selectedNode && (
            <div className="bg-white border border-blue-200 rounded-lg p-4 shadow-sm animate-in fade-in duration-200">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2 mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-blue-700">
                    Step Inspector: {selectedNode.label}
                  </span>
                  <span className="text-[11px] bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-mono font-medium">
                    Type: {selectedNode.type}
                  </span>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="text-xs text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  ✕ Close
                </button>
              </div>

              <div className="text-xs text-slate-700 space-y-2">
                <p><span className="font-semibold text-slate-900">Description:</span> {selectedNode.description}</p>
                {selectedNode.details && (
                  <pre className="bg-slate-50 p-2.5 rounded border border-slate-200 overflow-x-auto font-mono text-[11px] text-slate-700">
                    {JSON.stringify(selectedNode.details, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}

          {editing && (
            <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
              <h3 className="text-xs font-semibold text-slate-700">Edit Plan JSON</h3>
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className="input font-mono text-xs min-h-64"
              />
              <div className="flex gap-2">
                <button
                  disabled={busy}
                  onClick={() =>
                    runAction(async () => {
                      const parsed = JSON.parse(editText);
                      await api.editPlan(actorEmail, flowId, parsed);
                    })
                  }
                  className="btn-primary text-xs"
                >
                  Save edit
                </button>
                <button disabled={busy} onClick={() => setEditing(false)} className="btn-secondary text-xs">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: plan approved, ready to preview */}
      {status === "plan_approved" && (
        <Panel title="Step 2 · Run a preview">
          <p className="text-sm text-slate-600 mb-3">
            Runs the plan against a sample of real data - no full extract or publish happens yet.
          </p>
          <button disabled={busy} onClick={() => runAction(() => api.runPreview(actorEmail, flowId))} className="btn-primary">
            {busy ? "Running preview..." : "Run preview"}
          </button>
        </Panel>
      )}

      {/* Preview results */}
      {status === "preview_pending_approval" && latestPreviewRun && (
        <Panel title="Preview results">
          {latestPreviewRun.status === "failed" ? (
            <>
              <p className="text-sm text-red-700 mb-3">{latestPreviewRun.error_message}</p>
              <p className="text-sm text-slate-600">Edit the plan above and try again.</p>
            </>
          ) : (
            <div className="space-y-4">
              <div className="flex gap-6 text-sm">
                <span>
                  Rows before: <strong>{latestPreviewRun.rows_before}</strong>
                </span>
                <span>
                  Rows after: <strong>{latestPreviewRun.rows_after}</strong>
                </span>
              </div>

              {latestPreviewRun.row_count_anomaly && (
                <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded px-3 py-2">
                  Row count grew more than expected ({latestPreviewRun.rows_before} → {latestPreviewRun.rows_after}) -
                  a join may be fanning out unexpectedly. Review before approving.
                </div>
              )}

              <div>
                <h3 className="text-sm font-medium text-slate-600 mb-1">Sample before</h3>
                <DataTable rows={latestPreviewRun.sample_before} />
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-600 mb-1">Sample after</h3>
                <DataTable rows={latestPreviewRun.sample_after} />
              </div>

              {latestPreviewRun.row_count_anomaly && (
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={acknowledgeAnomaly}
                    onChange={(e) => setAcknowledgeAnomaly(e.target.checked)}
                  />
                  I reviewed the row-count growth and want to approve anyway
                </label>
              )}

              <button
                disabled={busy || (latestPreviewRun.row_count_anomaly && !acknowledgeAnomaly)}
                onClick={() => runAction(() => api.approvePreview(actorEmail, flowId, acknowledgeAnomaly))}
                className="btn-primary"
              >
                Approve preview
              </button>
            </div>
          )}
        </Panel>
      )}

      {/* Step 3: approved, ready to execute */}
      {status === "approved" && (
        <Panel title="Step 3 · Execute and publish">
          <p className="text-sm text-slate-600 mb-3">
            Runs the full plan, writes a .hyper extract, and publishes it to Tableau.
          </p>
          <button disabled={busy} onClick={() => runAction(() => api.executeFlow(actorEmail, flowId))} className="btn-primary">
            {busy ? "Executing..." : "Execute"}
          </button>
        </Panel>
      )}

      {status === "running" && (
        <Panel title="Running">
          <p className="text-sm text-slate-600">Executing the plan and publishing to Tableau...</p>
        </Panel>
      )}

      {status === "published" && latestExecuteRun && (
        <Panel title="Execution Complete">
          <p className="text-sm text-green-700 font-medium mb-3">
            ✓ Successfully executed transformation pipeline and generated Hyper extract!
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-slate-50 border border-slate-100 rounded p-3 mb-4 text-xs">
            <div>
              <span className="text-slate-500 block">Rows Before</span>
              <span className="font-semibold text-slate-800 text-sm">{latestExecuteRun.rows_before ?? "-"}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Rows After (Extracted)</span>
              <span className="font-semibold text-blue-700 text-sm">{latestExecuteRun.rows_after ?? "-"}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Publish Status</span>
              <span className="font-semibold text-slate-800 text-sm">{latestExecuteRun.publish_status ?? "-"}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Trigger Type</span>
              <span className="font-semibold text-purple-700 text-sm capitalize">{latestExecuteRun.trigger_type ?? "manual"}</span>
            </div>
          </div>

          {latestExecuteRun.sample_after && latestExecuteRun.sample_after.length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-slate-800 mb-2">Transformed Output Preview</h3>
              <DataTable rows={latestExecuteRun.sample_after} />
            </div>
          )}

          <dl className="text-xs text-slate-600 space-y-1 bg-slate-50 p-2.5 rounded border border-slate-100">
            <div>
              <dt className="inline font-medium text-slate-700">Hyper Extract File: </dt>
              <dd className="inline font-mono">{latestExecuteRun.hyper_file_path}</dd>
            </div>
          </dl>
        </Panel>
      )}

      {/* Automated Schedule Card */}
      <ScheduleCard
        flowId={flowId}
        schedule={schedule}
        onScheduleChanged={loadAll}
        disabled={status !== "approved" && status !== "published"}
      />
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-6">
      <h2 className="font-medium text-slate-900 mb-3">{title}</h2>
      {children}
    </div>
  );
}

"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import { useActor } from "@/lib/actor-context";
import type { FlowSchedule } from "@/lib/types";

export function ScheduleCard({
  flowId,
  schedule,
  onScheduleChanged,
  disabled = false,
}: {
  flowId: string;
  schedule: FlowSchedule | null;
  onScheduleChanged: () => Promise<void>;
  disabled?: boolean;
}) {
  const { actorEmail } = useActor();
  const [cron, setCron] = useState(schedule?.cron_expression ?? "0 5 * * *");
  const [timezone, setTimezone] = useState(
    schedule?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? "UTC"
  );
  const [enabled, setEnabled] = useState(schedule?.enabled ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      if (schedule) {
        await api.updateSchedule(actorEmail, flowId, {
          cron_expression: cron,
          timezone,
          enabled,
        });
      } else {
        await api.setSchedule(actorEmail, flowId, {
          cron_expression: cron,
          timezone,
          enabled,
        });
      }
      setSuccess("Schedule saved successfully!");
      await onScheduleChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save schedule");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Are you sure you want to remove this schedule?")) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await api.deleteSchedule(actorEmail, flowId);
      setSuccess("Schedule removed.");
      await onScheduleChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to remove schedule");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-medium text-slate-900">Automated Schedule</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Run this approved flow periodically and publish directly to Tableau without re-querying the LLM.
          </p>
        </div>
        {schedule && (
          <span
            className={`px-2 py-0.5 text-xs font-semibold rounded ${
              schedule.enabled
                ? "bg-green-100 text-green-800"
                : "bg-slate-100 text-slate-600"
            }`}
          >
            {schedule.enabled ? "Active" : "Paused"}
          </span>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          {error}
        </p>
      )}
      {success && (
        <p className="text-xs text-green-700 bg-green-50 border border-green-200 rounded p-2">
          {success}
        </p>
      )}

      {disabled ? (
        <p className="text-sm text-slate-500 italic">
          Schedule will become available once the flow plan and preview are approved.
        </p>
      ) : (
        <form onSubmit={handleSave} className="space-y-3">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="sched-enabled"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="sched-enabled" className="text-sm font-medium text-slate-700">
              Enable automated runs
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Cron Expression
              </label>
              <input
                type="text"
                value={cron}
                onChange={(e) => setCron(e.target.value)}
                placeholder="0 5 * * *"
                required
                className="w-full text-sm border border-slate-300 rounded px-2.5 py-1.5 focus:outline-none focus:border-blue-500 font-mono"
              />
              <span className="text-[11px] text-slate-400">e.g. &apos;0 5 * * *&apos; (Daily 5:00 AM)</span>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Timezone
              </label>
              <input
                type="text"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                placeholder="Asia/Kolkata or UTC"
                required
                className="w-full text-sm border border-slate-300 rounded px-2.5 py-1.5 focus:outline-none focus:border-blue-500 font-mono"
              />
              <span className="text-[11px] text-slate-400">e.g. Asia/Kolkata, UTC, America/New_York</span>
            </div>
          </div>

          {schedule && (
            <div className="text-xs text-slate-600 bg-slate-50 border border-slate-100 rounded p-3 space-y-1">
              {schedule.next_run_at ? (
                <div>
                  <span className="font-medium text-slate-700">Next Scheduled Run: </span>
                  <span className="text-blue-700 font-semibold">
                    {new Date(schedule.next_run_at).toLocaleString()}
                  </span>
                </div>
              ) : (
                <div className="text-slate-500">No upcoming run (schedule is disabled).</div>
              )}
              {schedule.last_run_at && (
                <div>
                  <span className="font-medium text-slate-700">Last Run: </span>
                  <span>{new Date(schedule.last_run_at).toLocaleString()}</span>
                  {schedule.last_run_status && (
                    <span
                      className={`ml-2 px-1.5 py-0.2 text-[10px] uppercase font-bold rounded ${
                        schedule.last_run_status === "succeeded"
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {schedule.last_run_status}
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center gap-2 pt-1">
            <button
              type="submit"
              disabled={busy}
              className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 font-medium cursor-pointer"
            >
              {busy ? "Saving..." : schedule ? "Update Schedule" : "Set Schedule"}
            </button>
            {schedule && (
              <button
                type="button"
                onClick={handleDelete}
                disabled={busy}
                className="px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded disabled:opacity-50 border border-red-200 cursor-pointer"
              >
                Delete
              </button>
            )}
          </div>
        </form>
      )}
    </div>
  );
}

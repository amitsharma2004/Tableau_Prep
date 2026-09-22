import type {
  Connection,
  ConnectionCreate,
  ConnectionTestResult,
  Flow,
  FlowCreate,
  PlanDraft,
  PlanVersion,
  Run,
  FlowSchedule,
  ScheduleCreateRequest,
  ScheduleUpdateRequest,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  actorEmail: string,
  options: { method?: string; body?: unknown } = {}
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Actor-Email": actorEmail,
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      // response wasn't JSON - keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Connections
  listConnections: (actorEmail: string) => request<Connection[]>("/connections", actorEmail),
  createConnection: (actorEmail: string, payload: ConnectionCreate) =>
    request<Connection>("/connections", actorEmail, { method: "POST", body: payload }),
  testConnection: (actorEmail: string, connectionId: string) =>
    request<ConnectionTestResult>(`/connections/${connectionId}/test`, actorEmail, { method: "POST" }),
  getConnectionSchema: (actorEmail: string, connectionId: string) =>
    request<ConnectionTestResult>(`/connections/${connectionId}/schema`, actorEmail),
  sampleTable: (actorEmail: string, connectionId: string, table: string, schema?: string, limit: number = 50) => {
    const params = new URLSearchParams({ table, limit: String(limit) });
    if (schema) params.set("schema", schema);
    return request<{ rows: Record<string, unknown>[] }>(`/connections/${connectionId}/sample?${params.toString()}`, actorEmail);
  },
  uploadFile: async (actorEmail: string, file: File, name?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    if (name) formData.append("name", name);
    const res = await fetch(`${API_BASE_URL}/connections/upload`, {
      method: "POST",
      headers: {
        "X-Actor-Email": actorEmail,
      },
      body: formData,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = await res.json();
        detail = data.detail ?? detail;
      } catch {}
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<Connection>;
  },

  // Flows
  listFlows: (actorEmail: string) => request<Flow[]>("/flows", actorEmail),
  getFlow: (actorEmail: string, flowId: string) => request<Flow>(`/flows/${flowId}`, actorEmail),
  createFlow: (actorEmail: string, payload: FlowCreate) =>
    request<Flow>("/flows", actorEmail, { method: "POST", body: payload }),
  generatePlan: (actorEmail: string, flowId: string, prompt?: string) =>
    request<PlanVersion>(`/flows/${flowId}/plan`, actorEmail, {
      method: "POST",
      body: prompt ? { prompt } : {},
    }),
  getActivePlan: (actorEmail: string, flowId: string) =>
    request<PlanVersion>(`/flows/${flowId}/plan`, actorEmail),
  editPlan: (
    actorEmail: string,
    flowId: string,
    plan: PlanDraft,
    changeSummary?: string,
    baseVersionId?: string,
  ) =>
    request<PlanVersion>(`/flows/${flowId}/plan`, actorEmail, {
      method: "PATCH",
      body: { plan, change_summary: changeSummary, base_version_id: baseVersionId },
    }),
  listVersions: (actorEmail: string, flowId: string) =>
    request<PlanVersion[]>(`/flows/${flowId}/versions`, actorEmail),
  restoreVersion: (actorEmail: string, flowId: string, versionId: string) =>
    request<PlanVersion>(`/flows/${flowId}/restore-version`, actorEmail, {
      method: "POST",
      body: { version_id: versionId },
    }),
  approvePlan: (actorEmail: string, flowId: string, versionId?: string) => {
    const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
    return request<PlanVersion>(`/flows/${flowId}/approve-plan${query}`, actorEmail, { method: "POST" });
  },
  runPreview: (actorEmail: string, flowId: string) =>
    request<Run>(`/flows/${flowId}/preview`, actorEmail, { method: "POST" }),
  approvePreview: (actorEmail: string, flowId: string, acknowledgeAnomaly = false) =>
    request<Run>(`/flows/${flowId}/approve-preview`, actorEmail, {
      method: "POST",
      body: { acknowledge_anomaly: acknowledgeAnomaly },
    }),
  previewStep: (actorEmail: string, flowId: string, alias: string, limit = 50) =>
    request<{ alias: string; rows: Record<string, unknown>[] }>(
      `/flows/${flowId}/preview-step?alias=${encodeURIComponent(alias)}&limit=${limit}`,
      actorEmail
    ),
  executeFlow: (actorEmail: string, flowId: string) =>
    request<Run>(`/flows/${flowId}/execute`, actorEmail, { method: "POST" }),
  getSchedule: (actorEmail: string, flowId: string) =>
    request<FlowSchedule | null>(`/flows/${flowId}/schedule`, actorEmail),
  setSchedule: (actorEmail: string, flowId: string, payload: ScheduleCreateRequest) =>
    request<FlowSchedule>(`/flows/${flowId}/schedule`, actorEmail, { method: "POST", body: payload }),
  updateSchedule: (actorEmail: string, flowId: string, payload: ScheduleUpdateRequest) =>
    request<FlowSchedule>(`/flows/${flowId}/schedule`, actorEmail, { method: "PATCH", body: payload }),
  deleteSchedule: (actorEmail: string, flowId: string) =>
    request<void>(`/flows/${flowId}/schedule`, actorEmail, { method: "DELETE" }),

  // Runs
  listRuns: (actorEmail: string, flowId?: string) =>
    request<Run[]>(`/runs${flowId ? `?flow_id=${flowId}` : ""}`, actorEmail),
  getRun: (actorEmail: string, runId: string) => request<Run>(`/runs/${runId}`, actorEmail),
};

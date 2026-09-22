"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import { useActor } from "@/lib/actor-context";
import type { Connection, ConnectionType } from "@/lib/types";

const EMPTY_FORM = {
  name: "",
  type: "postgres" as ConnectionType,
  host: "",
  port: 5432,
  database_name: "",
  username: "",
  secret: "",
  tableau_site_id: "",
  tableau_project_id: "",
};

export default function ConnectionsPage() {
  const { actorEmail } = useActor();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  async function load() {
    setLoading(true);
    try {
      setConnections(await api.listConnections(actorEmail));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load connections");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isDb = form.type === "postgres" || form.type === "mysql";
  const isSqlite = form.type === "sqlite";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createConnection(actorEmail, {
        name: form.name,
        type: form.type,
        host: isSqlite ? "localhost" : form.host,
        port: isSqlite ? 0 : Number(form.port),
        database_name: form.database_name || "n/a",
        username: isSqlite ? "sqlite" : form.username,
        secret: isSqlite ? "none" : form.secret,
        tableau_site_id: form.tableau_site_id || null,
        tableau_project_id: form.tableau_project_id || null,
      });
      setForm(EMPTY_FORM);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create connection");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTest(id: string) {
    setTestResults((prev) => ({ ...prev, [id]: "Testing..." }));
    try {
      const result = await api.testConnection(actorEmail, id);
      setTestResults((prev) => ({
        ...prev,
        [id]: `Connected. Read-only: ${result.is_read_only}. Tables found: ${result.tables.length}`,
      }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [id]: err instanceof ApiError ? `Failed: ${err.message}` : "Failed to test connection",
      }));
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Connections</h1>
        <p className="text-slate-600 mt-1">
          Connect to databases with read-only credentials or upload files (CSV, Excel, JSON) to start preparing data.
        </p>
      </div>

      {/* File Upload Data Source Card */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-5 max-w-2xl shadow-xs">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-blue-950 flex items-center gap-2">
              <span className="p-1 bg-blue-600 text-white rounded">
                📁
              </span>
              Upload File Source (CSV, Excel, JSON)
            </h2>
            <p className="text-xs text-blue-800/80 mt-1">
              Directly upload your tabular files — they are automatically parsed and converted into queryable datasets.
            </p>
          </div>
          <div>
            <label className="cursor-pointer px-4 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-all shadow-sm flex items-center gap-1.5">
              <span>{submitting ? "Uploading..." : "Choose File"}</span>
              <input
                type="file"
                disabled={submitting}
                accept=".csv,.xlsx,.xls,.json,.txt"
                className="hidden"
                onChange={async (e) => {
                  const files = e.target.files;
                  if (!files || files.length === 0) return;
                  setSubmitting(true);
                  setError(null);
                  try {
                    await api.uploadFile(actorEmail, files[0]);
                    await load();
                  } catch (err) {
                    setError(err instanceof ApiError ? err.message : "Failed to upload file");
                  } finally {
                    setSubmitting(false);
                    e.target.value = "";
                  }
                }}
              />
            </label>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-lg p-6 space-y-4 max-w-2xl">
        <h2 className="font-medium text-slate-900">New Database Connection</h2>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Name">
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="input"
            />
          </Field>
          <Field label="Type">
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value as ConnectionType })}
              className="input"
            >
              <option value="postgres">PostgreSQL</option>
              <option value="mysql">MySQL</option>
              <option value="sqlite">SQLite (Local Database)</option>
              <option value="tableau_server">Tableau Server / Cloud</option>
            </select>
          </Field>
        </div>

        {isSqlite ? (
          <Field label="SQLite Database File Path">
            <input
              required
              value={form.database_name}
              onChange={(e) => setForm({ ...form, database_name: e.target.value })}
              placeholder="/absolute/path/to/analytics.db"
              className="input"
            />
            <p className="text-xs text-slate-500 mt-1">Absolute file path on the server or relative to backend directory.</p>
          </Field>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4">
              <Field label={isDb ? "Host" : "Server URL"}>
                <input
                  required
                  value={form.host}
                  onChange={(e) => setForm({ ...form, host: e.target.value })}
                  placeholder={isDb ? "db.internal" : "https://xyz.online.tableau.com"}
                  className="input"
                />
              </Field>
              <Field label="Port">
                <input
                  type="number"
                  required={isDb}
                  value={form.port}
                  onChange={(e) => setForm({ ...form, port: Number(e.target.value) })}
                  className="input"
                />
              </Field>
            </div>

            {isDb ? (
              <div className="grid grid-cols-2 gap-4">
                <Field label="Database name">
                  <input
                    required
                    value={form.database_name}
                    onChange={(e) => setForm({ ...form, database_name: e.target.value })}
                    className="input"
                  />
                </Field>
                <Field label="Read-only username">
                  <input
                    required
                    value={form.username}
                    onChange={(e) => setForm({ ...form, username: e.target.value })}
                    className="input"
                  />
                </Field>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-4">
                <Field label="PAT name">
                  <input
                    required
                    value={form.username}
                    onChange={(e) => setForm({ ...form, username: e.target.value })}
                    className="input"
                  />
                </Field>
                <Field label="Site ID">
                  <input
                    value={form.tableau_site_id}
                    onChange={(e) => setForm({ ...form, tableau_site_id: e.target.value })}
                    className="input"
                  />
                </Field>
                <Field label="Project ID">
                  <input
                    value={form.tableau_project_id}
                    onChange={(e) => setForm({ ...form, tableau_project_id: e.target.value })}
                    className="input"
                  />
                </Field>
              </div>
            )}

            <Field label={isDb ? "Password" : "Personal access token secret"}>
              <input
                type="password"
                required
                value={form.secret}
                onChange={(e) => setForm({ ...form, secret: e.target.value })}
                className="input"
              />
            </Field>
          </>
        )}

        {error && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}

        <button type="submit" disabled={submitting} className="btn-primary">
          {submitting ? "Creating..." : "Create connection"}
        </button>
      </form>

      <div>
        <h2 className="font-medium text-slate-900 mb-3">Existing connections</h2>
        {loading ? (
          <p className="text-slate-500 text-sm">Loading...</p>
        ) : connections.length === 0 ? (
          <p className="text-slate-500 text-sm">No connections yet.</p>
        ) : (
          <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-100">
            {connections.map((c) => (
              <div key={c.id} className="p-4 flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-slate-900">{c.name}</p>
                  <p className="text-sm text-slate-500">
                    {c.type} · {c.host} {c.is_read_only ? "· read-only" : ""}
                  </p>
                  {testResults[c.id] && <p className="text-xs text-slate-500 mt-1">{testResults[c.id]}</p>}
                </div>
                <button onClick={() => handleTest(c.id)} className="btn-secondary shrink-0">
                  Test connection
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-700 mb-1">{label}</span>
      {children}
    </label>
  );
}

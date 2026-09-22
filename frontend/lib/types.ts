// Mirrors backend/app/schemas/*.py and backend/app/llm/plan_schema.py.
// Kept as plain types (no zod) - the backend is the source of truth for
// validation; the frontend just needs to render/edit these shapes.

export type ConnectionType = "postgres" | "mysql" | "sqlite" | "tableau_server";

export interface Connection {
  id: string;
  name: string;
  type: ConnectionType;
  host: string | null;
  port: number | null;
  database_name: string | null;
  username: string | null;
  is_read_only: boolean;
  tableau_site_id: string | null;
  tableau_project_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ConnectionCreate {
  name: string;
  type: ConnectionType;
  host: string;
  port: number;
  database_name: string;
  username: string;
  secret: string;
  tableau_site_id?: string | null;
  tableau_project_id?: string | null;
}

export interface ColumnSchema {
  name: string;
  data_type: string;
  nullable: boolean;
}

export interface TableSchema {
  name: string;
  schema: string;
  columns: ColumnSchema[];
}

export interface ConnectionTestResult {
  connected: boolean;
  is_read_only: boolean;
  tables: TableSchema[];
}

export type FlowStatus =
  | "draft"
  | "plan_pending_approval"
  | "plan_approved"
  | "preview_pending_approval"
  | "approved"
  | "running"
  | "published"
  | "failed";

export interface Flow {
  id: string;
  name: string;
  nl_request: string;
  source_connection_id: string;
  tableau_connection_id: string | null;
  target_datasource_name: string | null;
  status: FlowStatus;
  current_version_id?: string | null;
  approved_version_id?: string | null;
  active_plan_version_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface FlowCreate {
  name: string;
  nl_request: string;
  source_connection_id: string;
  tableau_connection_id?: string | null;
  target_datasource_name?: string | null;
}

// --- Plan step union - mirrors app/llm/plan_schema.py ---

export interface SourceTableRef {
  alias: string;
  schema_name: string;
  table_name: string;
}

export interface FilterCondition {
  column: string;
  operator: "=" | "!=" | ">" | "<" | ">=" | "<=" | "is_null" | "is_not_null" | "in";
  value?: unknown;
}

export interface FilterStep {
  type: "filter";
  target: string;
  output_alias: string;
  conditions: FilterCondition[];
  logic: "and" | "or";
}

export interface DropNullsStep {
  type: "drop_nulls";
  target: string;
  output_alias: string;
  columns: string[];
}

export interface DedupeStep {
  type: "dedupe";
  target: string;
  output_alias: string;
  columns: string[] | null;
}

export interface JoinStep {
  type: "join";
  left: string;
  right: string;
  join_type: "inner" | "left" | "right" | "full";
  on: string[][];
  output_alias: string;
}

export interface RenameStep {
  type: "rename";
  target: string;
  output_alias: string;
  mapping: Record<string, string>;
}

export interface SelectColumnsStep {
  type: "select_columns";
  target: string;
  output_alias: string;
  columns: string[];
}

export interface AggregationSpec {
  column: string;
  function: "sum" | "avg" | "count" | "min" | "max";
  alias: string;
}

export interface AggregateStep {
  type: "aggregate";
  target: string;
  output_alias: string;
  group_by: string[];
  aggregations: AggregationSpec[];
}

export interface CastStep {
  type: "cast";
  target: string;
  output_alias: string;
  mapping: Record<string, "string" | "integer" | "float" | "date" | "boolean">;
}

export interface TextCleanStep {
  type: "text_clean";
  target: string;
  output_alias: string;
  operations: Record<string, "trim" | "upper" | "lower">;
}

export interface UnionStep {
  type: "union";
  inputs: string[];
  output_alias: string;
  distinct?: boolean;
}

export type PlanStep =
  | FilterStep
  | DropNullsStep
  | DedupeStep
  | JoinStep
  | UnionStep
  | RenameStep
  | SelectColumnsStep
  | AggregateStep
  | CastStep
  | TextCleanStep;

export interface PlanDraft {
  summary: string;
  sources: SourceTableRef[];
  steps: PlanStep[];
  output_alias: string;
}

export interface PlanVersion {
  id: string;
  flow_id: string;
  version_number: number;
  source: "llm_generated" | "human_edited";
  parent_version_id?: string | null;
  change_summary?: string | null;
  plan: PlanDraft;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface Run {
  id: string;
  flow_id: string;
  plan_version_id: string;
  run_type: "preview" | "execute";
  status: "running" | "succeeded" | "failed";
  generated_sql: string | null;
  generated_code_lang: string | null;
  rows_before: number | null;
  rows_after: number | null;
  row_count_anomaly: boolean;
  sample_before: Record<string, unknown>[] | null;
  sample_after: Record<string, unknown>[] | null;
  hyper_file_path: string | null;
  publish_status: string | null;
  publish_error: string | null;
  error_message: string | null;
  trigger_type?: "manual" | "scheduled";
  scheduled_for?: string | null;
  started_at: string;
  finished_at: string | null;
  triggered_by: string;
}

export interface FlowSchedule {
  id: string;
  flow_id: string;
  plan_version_id: string;
  enabled: boolean;
  cron_expression: string;
  timezone: string;
  next_run_at: string | null;
  last_run_at: string | null;
  last_run_status: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ScheduleCreateRequest {
  cron_expression: string;
  timezone: string;
  enabled?: boolean;
}

export interface ScheduleUpdateRequest {
  cron_expression?: string;
  timezone?: string;
  enabled?: boolean;
}

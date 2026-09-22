"use client";

import { useEffect, useState, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import { useActor } from "@/lib/actor-context";
import type { Connection, Flow, PlanVersion, Run } from "@/lib/types";
import { VisualFlowCanvas } from "@/components/visual-flow-canvas";
import { TableauDataProfiler } from "@/components/tableau-data-profiler";
import { TableauStepChanges } from "@/components/tableau-step-changes";
import { DataTable } from "@/components/data-table";
import { StatusBadge } from "@/components/status-badge";
import { JoinConfigModal } from "@/components/join-config-modal";
import { StepActionModal } from "@/components/step-action-modal";
import type { PrepNodeData } from "@/lib/plan-to-graph";
import {
  Sparkles,
  Play,
  CloudUpload,
  Send,
  MessageSquare,
  CheckCircle2,
  AlertCircle,
  Database,
  RefreshCw,
  Maximize2,
  Minimize2,
  ChevronRight,
  ChevronLeft,
  Eye,
  Table,
  X,
  Search,
  Plus,
  Layers,
  ChevronDown,
  Download,
  Upload,
  Save,
  Check,
  History,
} from "lucide-react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

function FlowStudioContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const flowIdParam = searchParams.get("flowId");

  const { actorEmail } = useActor();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [databaseTables, setDatabaseTables] = useState<any[]>([]);
  const [tableSearch, setTableSearch] = useState<string>("");
  const [isLoadingTables, setIsLoadingTables] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);

  const [currentFlow, setCurrentFlow] = useState<Flow | null>(null);
  const [activePlan, setActivePlan] = useState<PlanVersion | null>(null);
  const [draftPlan, setDraftPlan] = useState<any | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const [isSavingCheckpoint, setIsSavingCheckpoint] = useState<boolean>(false);
  const [isApprovingPlan, setIsApprovingPlan] = useState<boolean>(false);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState<boolean>(false);
  const [versionHistory, setVersionHistory] = useState<PlanVersion[]>([]);
  const [latestPreviewRun, setLatestPreviewRun] = useState<Run | null>(null);
  const [latestExecuteRun, setLatestExecuteRun] = useState<Run | null>(null);

  const [promptInput, setPromptInput] = useState("");
  const [isAiGenerating, setIsAiGenerating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publishSuccess, setPublishSuccess] = useState<string | null>(null);

  const [selectedNode, setSelectedNode] = useState<PrepNodeData | null>(null);
  const [isCopilotOpen, setIsCopilotOpen] = useState(true);
  const previewDrawerRef = useRef<HTMLDivElement>(null);

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      role: "assistant",
      content:
        "👋 Welcome to Tableau AI Prep Studio! Select a source database and tell me how you want to prepare, join, or clean your data.",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);

  const [isUploadingFile, setIsUploadingFile] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load connections on mount
  async function refreshConnections() {
    const conns = await api.listConnections(actorEmail);
    setConnections(conns);
    return conns;
  }

  useEffect(() => {
    refreshConnections().then((conns) => {
      const sourceConn = conns.find((c) => c.type === "sqlite" || c.type === "postgres" || c.type === "mysql");
      if (sourceConn && !selectedConnectionId) setSelectedConnectionId(sourceConn.id);
    });
  }, [actorEmail]);

  // Load flow if flowId exists in URL query parameter (persistence on refresh)
  useEffect(() => {
    if (!flowIdParam) return;
    api
      .getFlow(actorEmail, flowIdParam)
      .then(async (flow) => {
        setCurrentFlow(flow);
        if (flow.source_connection_id) {
          setSelectedConnectionId(flow.source_connection_id);
        }
        if (flow.active_plan_version_id || flow.current_version_id) {
          try {
            const planVer = await api.getActivePlan(actorEmail, flow.id);
            setActivePlan(planVer);
            setDraftPlan(planVer.plan);
            setHasUnsavedChanges(false);
          } catch (err) {
            console.error("Failed to load active plan for flow:", err);
          }
        }
      })
      .catch((err) => {
        console.error("Failed to restore flow from URL param:", err);
      });
  }, [actorEmail, flowIdParam]);

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    setIsUploadingFile(true);
    setError(null);
    try {
      const newConn = await api.uploadFile(actorEmail, file);
      const conns = await refreshConnections();
      setSelectedConnectionId(newConn.id);
      // Auto-load schema for newly uploaded connection
      const schema = await api.getConnectionSchema(actorEmail, newConn.id);
      setDatabaseTables(schema.tables || []);
    } catch (err) {
      console.error("Failed to upload file:", err);
      setError(err instanceof ApiError ? err.message : "Failed to upload file");
    } finally {
      setIsUploadingFile(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  // Load database tables whenever selectedConnectionId changes
  useEffect(() => {
    if (!selectedConnectionId) {
      setDatabaseTables([]);
      return;
    }
    setIsLoadingTables(true);
    api
      .getConnectionSchema(actorEmail, selectedConnectionId)
      .then((res) => {
        setDatabaseTables(res.tables || []);
      })
      .catch((err) => {
        console.error("Failed to load tables schema:", err);
      })
      .finally(() => {
        setIsLoadingTables(false);
      });
  }, [actorEmail, selectedConnectionId]);

  async function handleSendPrompt(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const prompt = promptInput.trim();
    if (!prompt) return;

    if (!selectedConnectionId) {
      setError("Please select a source database connection first.");
      return;
    }

    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: "user",
      content: prompt,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setPromptInput("");
    setIsAiGenerating(true);
    setError(null);

    try {
      let flow = currentFlow;
      if (!flow) {
        flow = await api.createFlow(actorEmail, {
          name: prompt.length > 30 ? `${prompt.slice(0, 30)}...` : prompt,
          nl_request: prompt,
          source_connection_id: selectedConnectionId,
        });
        setCurrentFlow(flow);
        window.history.replaceState(null, "", `/flows/new?flowId=${flow.id}`);
      }

      const planVer = await api.generatePlan(actorEmail, flow.id, prompt);
      setActivePlan(planVer);

      flow = await api.getFlow(actorEmail, flow.id);
      setCurrentFlow(flow);

      const assistantMsg: ChatMessage = {
        id: String(Date.now() + 1),
        role: "assistant",
        content: `✨ Visual Prep Flow generated!\n- Sources: ${planVer.plan.sources.map((s) => s.table_name).join(", ")}\n- Transformations: ${planVer.plan.steps.map((s) => s.type).join(" ➔ ")}\n- Output: ${planVer.plan.output_alias}\n\nYou can click any step in the canvas to inspect live profiling data or click **Run Flow** to execute transformations.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setChatMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate flow");
      setChatMessages((prev) => [
        ...prev,
        {
          id: String(Date.now() + 1),
          role: "assistant",
          content: `⚠️ Error: ${err instanceof ApiError ? err.message : "Plan generation failed."}`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setIsAiGenerating(false);
    }
  }

  async function handleRunFlow() {
    if (!currentFlow) return;
    setIsRunning(true);
    setError(null);
    setPublishSuccess(null);
    try {
      let flow = currentFlow;

      if (flow.status === "plan_pending_approval") {
        await api.approvePlan(actorEmail, flow.id);
        flow = await api.getFlow(actorEmail, flow.id);
        setCurrentFlow(flow);
      }

      let prevRun = latestPreviewRun;
      if (flow.status === "plan_approved" || flow.status === "failed") {
        prevRun = await api.runPreview(actorEmail, flow.id);
        setLatestPreviewRun(prevRun);
        flow = await api.getFlow(actorEmail, flow.id);
        setCurrentFlow(flow);
      }

      if (flow.status === "preview_pending_approval") {
        await api.approvePreview(actorEmail, flow.id, true);
        flow = await api.getFlow(actorEmail, flow.id);
        setCurrentFlow(flow);
      }

      if (prevRun?.sample_after && prevRun.sample_after.length > 0) {
        setNodeDataRows(prevRun.sample_after);
        setSelectedNode({
          label: "Tableau Hyper Extract (Transformed Output)",
          type: "output",
          alias: activePlan?.plan?.output_alias || "output",
          description: `Run succeeded: ${prevRun.rows_after ?? prevRun.sample_after.length} rows produced`,
        });

        // Auto scroll up to live preview drawer
        setTimeout(() => {
          previewDrawerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 100);
      }

      setChatMessages((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          role: "assistant",
          content: `✅ **Flow run completed successfully!**\n- Transformed records generated: **${prevRun?.rows_after ?? prevRun?.sample_after?.length ?? 0} rows**\n- Hyper extract preview ready for Tableau publishing.\n- Inspect the data profile cards below.`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch (err) {
      console.error("Run error:", err);
      setError(err instanceof ApiError ? err.message : "Run execution failed");
    } finally {
      setIsRunning(false);
    }
  }

  async function handlePublish() {
    if (!currentFlow) return;
    setIsPublishing(true);
    setError(null);
    setPublishSuccess(null);
    try {
      let flow = currentFlow;

      if (flow.status === "plan_pending_approval") {
        await api.approvePlan(actorEmail, flow.id);
        flow = await api.getFlow(actorEmail, flow.id);
        setCurrentFlow(flow);
      }

      if (flow.status === "plan_approved") {
        await api.runPreview(actorEmail, flow.id);
        flow = await api.getFlow(actorEmail, flow.id);
        setCurrentFlow(flow);
      }

      if (flow.status === "preview_pending_approval") {
        await api.approvePreview(actorEmail, flow.id, true);
        flow = await api.getFlow(actorEmail, flow.id);
        setCurrentFlow(flow);
      }

      const exec = await api.executeFlow(actorEmail, flow.id);
      setLatestExecuteRun(exec);
      setPublishSuccess(
        `Successfully published! Hyper extract written at: ${exec.hyper_file_path}`
      );
      if (exec.sample_after && exec.sample_after.length > 0) {
        setNodeDataRows(exec.sample_after);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Publish failed");
    } finally {
      setIsPublishing(false);
    }
  }

  function exportToCsv(rows: Record<string, unknown>[] | null, filename: string = "export.csv") {
    if (!rows || rows.length === 0) return;
    const headers = Object.keys(rows[0]);
    const csvContent = [
      headers.join(","),
      ...rows.map((row) =>
        headers
          .map((header) => {
            const val = row[header];
            if (val === null || val === undefined) return "";
            const strVal = String(val).replace(/"/g, '""');
            return `"${strVal}"`;
          })
          .join(",")
      ),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  // Keep draftPlan in sync when activePlan is updated from backend
  useEffect(() => {
    if (activePlan?.plan) {
      setDraftPlan(activePlan.plan);
      setHasUnsavedChanges(false);
    }
  }, [activePlan]);

  const displayPlan = draftPlan || activePlan?.plan;

  // Save Checkpoint: commits draftPlan to flow_plan_versions
  async function handleSaveCheckpoint(summary?: string) {
    if (!currentFlow || !draftPlan) return;
    setIsSavingCheckpoint(true);
    setError(null);
    try {
      const changeSummary = summary || `Saved checkpoint (${new Date().toLocaleTimeString()})`;
      const updatedVersion = await api.editPlan(
        actorEmail,
        currentFlow.id,
        draftPlan,
        changeSummary,
        activePlan?.id
      );
      setActivePlan(updatedVersion);
      setDraftPlan(updatedVersion.plan);
      setHasUnsavedChanges(false);

      const refreshedFlow = await api.getFlow(actorEmail, currentFlow.id);
      setCurrentFlow(refreshedFlow);

      // Refresh version list if modal is open
      if (isHistoryModalOpen) {
        const history = await api.listVersions(actorEmail, currentFlow.id);
        setVersionHistory(history);
      }
    } catch (err) {
      console.error("Failed to save checkpoint:", err);
      setError(err instanceof ApiError ? err.message : "Failed to save checkpoint");
    } finally {
      setIsSavingCheckpoint(false);
    }
  }

  // Approve current or active version for production run/schedule
  async function handleApproveCurrentPlan() {
    if (!currentFlow || !activePlan) return;
    setIsApprovingPlan(true);
    setError(null);
    try {
      // If there are unsaved draft changes, save checkpoint first
      if (hasUnsavedChanges && draftPlan) {
        await handleSaveCheckpoint("Auto-saved before approval");
      }
      await api.approvePlan(actorEmail, currentFlow.id, activePlan.id);
      const refreshedFlow = await api.getFlow(actorEmail, currentFlow.id);
      setCurrentFlow(refreshedFlow);
    } catch (err) {
      console.error("Failed to approve plan:", err);
      setError(err instanceof ApiError ? err.message : "Failed to approve plan");
    } finally {
      setIsApprovingPlan(false);
    }
  }

  // Open Version History Modal
  async function handleOpenHistoryModal() {
    if (!currentFlow) return;
    setIsHistoryModalOpen(true);
    try {
      const history = await api.listVersions(actorEmail, currentFlow.id);
      setVersionHistory(history);
    } catch (err) {
      console.error("Failed to fetch version history:", err);
    }
  }

  // Restore a past version (creates new immutable version with that plan_json)
  async function handleRestoreVersion(versionId: string) {
    if (!currentFlow) return;
    try {
      const restored = await api.restoreVersion(actorEmail, currentFlow.id, versionId);
      setActivePlan(restored);
      setDraftPlan(restored.plan);
      setHasUnsavedChanges(false);

      const refreshedFlow = await api.getFlow(actorEmail, currentFlow.id);
      setCurrentFlow(refreshedFlow);

      const history = await api.listVersions(actorEmail, currentFlow.id);
      setVersionHistory(history);
    } catch (err) {
      console.error("Failed to restore version:", err);
      setError(err instanceof ApiError ? err.message : "Failed to restore version");
    }
  }

  // Global Ctrl+S / Cmd+S shortcut to save checkpoint
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (hasUnsavedChanges && currentFlow && draftPlan) {
          handleSaveCheckpoint();
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [hasUnsavedChanges, currentFlow, draftPlan, activePlan]);

  const [nodeDataRows, setNodeDataRows] = useState<Record<string, unknown>[] | null>(null);
  const [isLoadingNodeData, setIsLoadingNodeData] = useState(false);

  async function handleAddTableToCanvas(tableName: string, schemaName: string = "main") {
    try {
      if (!selectedConnectionId) {
        setError("Please select or upload a data source connection first.");
        return;
      }

      let flow = currentFlow;
      if (!flow) {
        flow = await api.createFlow(actorEmail, {
          name: `Flow with ${tableName}`,
          nl_request: `Analyze ${tableName}`,
          source_connection_id: selectedConnectionId,
        });
        setCurrentFlow(flow);
        window.history.replaceState(null, "", `/flows/new?flowId=${flow.id}`);
      }

      // Check if table is already in current plan
      const basePlan = draftPlan || activePlan?.plan || { sources: [], steps: [], output_alias: "" };
      const existingSources = basePlan.sources || [];
      const alreadyExists = existingSources.some((s: any) => s.table_name === tableName);
      if (alreadyExists) {
        const sourceNode = {
          label: tableName,
          type: "source",
          alias: tableName,
          description: `${schemaName}.${tableName}`,
          details: { schema: schemaName, table: tableName },
        } as PrepNodeData;
        handleNodeSelect(sourceNode);
        return;
      }

      const newAlias = tableName.toLowerCase();
      const updatedSources = [
        ...existingSources,
        { alias: newAlias, schema_name: schemaName, table_name: tableName },
      ];

      const currentSteps = basePlan.steps || [];
      const outputAlias = basePlan.output_alias || newAlias;

      const newPlanDraft = {
        sources: updatedSources,
        steps: currentSteps,
        output_alias: outputAlias,
        summary: `Added ${tableName} as a data source to the workflow.`,
      };

      // Set local draft plan and mark unsaved
      setDraftPlan(newPlanDraft);
      setHasUnsavedChanges(true);

      // Select newly added table node
      handleNodeSelect({
        label: tableName,
        type: "source",
        alias: newAlias,
        description: `${schemaName}.${tableName}`,
        details: { schema: schemaName, table: tableName },
      } as PrepNodeData);
    } catch (err) {
      console.error("Failed to add table to canvas:", err);
      setError(err instanceof ApiError ? err.message : "Failed to add table to flow");
    }
  }

  // State for Tableau-like interactive table connection / join modal
  const [joinModalConfig, setJoinModalConfig] = useState<{
    isOpen: boolean;
    leftTable: string;
    rightTable: string;
    leftColumns: string[];
    rightColumns: string[];
  }>({
    isOpen: false,
    leftTable: "",
    rightTable: "",
    leftColumns: [],
    rightColumns: [],
  });

  // Trace columns for any alias (raw table or intermediate step)
  function getColumnsForAlias(alias: string): string[] {
    if (!alias) return [];
    // 1. Direct match with a plan source
    const src = activePlan?.plan?.sources?.find(
      (s) => s.alias.toLowerCase() === alias.toLowerCase()
    );
    if (src) {
      const dbTable = databaseTables.find(
        (t) => t.name.toLowerCase() === src.table_name.toLowerCase()
      );
      if (dbTable?.columns && dbTable.columns.length > 0) {
        return dbTable.columns.map((c: any) => c.name);
      }
    }

    // 2. Direct match with database table name
    const dbTable = databaseTables.find(
      (t) => t.name.toLowerCase() === alias.toLowerCase()
    );
    if (dbTable?.columns && dbTable.columns.length > 0) {
      return dbTable.columns.map((c: any) => c.name);
    }

    // 3. Match with a plan step (filter, rename, drop_nulls, select_columns, join, etc.)
    const step = activePlan?.plan?.steps?.find(
      (s) => s.output_alias.toLowerCase() === alias.toLowerCase()
    );
    if (step) {
      if (step.type === "select_columns" && step.columns) {
        return step.columns;
      }
      if (step.type === "rename" && step.mapping) {
        const parentCols = getColumnsForAlias(step.target);
        return parentCols.map((c) => step.mapping[c] || c);
      }
      if ("target" in step && step.target) {
        return getColumnsForAlias(step.target);
      }
      if (step.type === "join") {
        const leftCols = getColumnsForAlias(step.left);
        const rightCols = getColumnsForAlias(step.right);
        return Array.from(new Set([...leftCols, ...rightCols]));
      }
    }

    // 4. Fallback search: extract prefix if e.g. customers_cleaned -> customers
    const prefixMatch = databaseTables.find((t) =>
      alias.toLowerCase().startsWith(t.name.toLowerCase())
    );
    if (prefixMatch?.columns && prefixMatch.columns.length > 0) {
      return prefixMatch.columns.map((c: any) => c.name);
    }

    // 5. Default common columns fallback
    return ["id", "customer_id", "order_id", "product_id", "status"];
  }

  // Triggered when user connects a line from one table/step to another in ReactFlow
  function handleConnectNodes(sourceAlias: string, targetAlias: string) {
    const leftCols = getColumnsForAlias(sourceAlias);
    const rightCols = getColumnsForAlias(targetAlias);

    setJoinModalConfig({
      isOpen: true,
      leftTable: sourceAlias,
      rightTable: targetAlias,
      leftColumns: leftCols,
      rightColumns: rightCols,
    });
  }

  async function handleApplyJoin(config: {
    joinType: "inner" | "left" | "right" | "full";
    leftCol: string;
    rightCol: string;
    outputAlias: string;
  }) {
    if (!currentFlow) return;
    try {
      const basePlan = draftPlan || activePlan?.plan || { sources: [], steps: [], output_alias: "" };
      const currentSources = basePlan.sources || [];
      const currentSteps = basePlan.steps || [];

      const newJoinStep = {
        type: "join" as const,
        left: joinModalConfig.leftTable,
        right: joinModalConfig.rightTable,
        join_type: config.joinType,
        on: [[config.leftCol, config.rightCol]],
        output_alias: config.outputAlias,
      };

      const newPlanDraft = {
        sources: currentSources,
        steps: [...currentSteps, newJoinStep],
        output_alias: config.outputAlias,
        summary: `Joined ${joinModalConfig.leftTable} and ${joinModalConfig.rightTable} on ${config.leftCol} = ${config.rightCol} (${config.joinType} join).`,
      };

      setDraftPlan(newPlanDraft);
      setHasUnsavedChanges(true);

      // Select newly added join node
      handleNodeSelect({
        label: config.outputAlias,
        type: "join",
        alias: config.outputAlias,
        description: `${config.joinType.toUpperCase()} join of ${joinModalConfig.leftTable} and ${joinModalConfig.rightTable}`,
        details: newJoinStep as unknown as Record<string, unknown>,
      } as PrepNodeData);
    } catch (err) {
      console.error("Failed to add join step:", err);
      setError(err instanceof ApiError ? err.message : "Failed to add join to flow");
    }
  }

  async function handleApplyUnion(config: {
    inputs: string[];
    distinct: boolean;
    outputAlias: string;
  }) {
    if (!currentFlow) return;
    try {
      const basePlan = draftPlan || activePlan?.plan || { sources: [], steps: [], output_alias: "" };
      const currentSources = basePlan.sources || [];
      const currentSteps = basePlan.steps || [];

      const newUnionStep = {
        type: "union" as const,
        inputs: config.inputs,
        distinct: config.distinct,
        output_alias: config.outputAlias,
      };

      const newPlanDraft = {
        sources: currentSources,
        steps: [...currentSteps, newUnionStep],
        output_alias: config.outputAlias,
        summary: `Stacked datasets ${config.inputs.join(" and ")} (${config.distinct ? "UNION" : "UNION ALL"}).`,
      };

      setDraftPlan(newPlanDraft);
      setHasUnsavedChanges(true);

      // Select newly added union node
      handleNodeSelect({
        label: config.outputAlias,
        type: "union",
        alias: config.outputAlias,
        description: `Union stack of ${config.inputs.join(", ")}`,
        details: newUnionStep as unknown as Record<string, unknown>,
      } as PrepNodeData);
    } catch (err) {
      console.error("Failed to add union step:", err);
      setError(err instanceof ApiError ? err.message : "Failed to add union to flow");
    }
  }

  // State for Tableau-like Clean / Rename / Filter / Remove column Step on Arrow (+ sign)
  const [stepActionModal, setStepActionModal] = useState<{
    isOpen: boolean;
    sourceAlias: string;
    targetAlias: string;
    columns: string[];
  }>({
    isOpen: false,
    sourceAlias: "",
    targetAlias: "",
    columns: [],
  });

  function handleAddStepOnEdge(sourceAlias: string, targetAlias: string) {
    const cols = getColumnsForAlias(sourceAlias);
    setStepActionModal({
      isOpen: true,
      sourceAlias,
      targetAlias,
      columns: cols,
    });
  }

  async function handleApplyCustomStep(newStep: any) {
    if (!currentFlow) return;
    try {
      const basePlan = draftPlan || activePlan?.plan || { sources: [], steps: [], output_alias: "" };
      const currentSources = basePlan.sources || [];
      const currentSteps = [...(basePlan.steps || [])];

      // Update any downstream step that previously referenced sourceAlias (if needed) or append step
      const oldAlias = stepActionModal.sourceAlias;
      const newAlias = newStep.output_alias;

      // Rewire downstream steps if targetAlias was consuming oldAlias
      currentSteps.forEach((step: any) => {
        if (step.type === "join") {
          if (step.left === oldAlias && step.output_alias === stepActionModal.targetAlias) {
            step.left = newAlias;
          }
          if (step.right === oldAlias && step.output_alias === stepActionModal.targetAlias) {
            step.right = newAlias;
          }
        } else if ("target" in step && step.target === oldAlias && step.output_alias === stepActionModal.targetAlias) {
          step.target = newAlias;
        }
      });

      // Insert new transformation step
      currentSteps.push(newStep);

      // If sourceAlias was the output_alias, update output_alias to newAlias
      let outputAlias = basePlan.output_alias;
      if (outputAlias === oldAlias) {
        outputAlias = newAlias;
      }

      const newPlanDraft = {
        sources: currentSources,
        steps: currentSteps,
        output_alias: outputAlias,
        summary: `Added ${newStep.type} step on ${oldAlias} (output: ${newAlias}).`,
      };

      setDraftPlan(newPlanDraft);
      setHasUnsavedChanges(true);

      // Select newly added step node
      handleNodeSelect({
        label: newAlias,
        type: newStep.type,
        alias: newAlias,
        description: `Applied ${newStep.type} on ${oldAlias}`,
        details: newStep as Record<string, unknown>,
      } as PrepNodeData);
    } catch (err) {
      console.error("Failed to insert step on edge:", err);
      setError(err instanceof ApiError ? err.message : "Failed to add step to flow");
    }
  }

  async function handleDeleteStep(aliasToDelete: string) {
    if (!currentFlow) return;
    try {
      const basePlan = draftPlan || activePlan?.plan || { sources: [], steps: [], output_alias: "" };
      const currentSources = basePlan.sources || [];
      const currentSteps = [...(basePlan.steps || [])];

      const stepIndex = currentSteps.findIndex((s: any) => s.output_alias === aliasToDelete);
      if (stepIndex === -1) return;

      const stepToDelete = currentSteps[stepIndex];
      // Find parent input alias for the step being deleted
      let parentAlias = "";
      if (stepToDelete.type === "join") {
        parentAlias = stepToDelete.left;
      } else if ("target" in stepToDelete && stepToDelete.target) {
        parentAlias = stepToDelete.target;
      }

      if (!parentAlias && currentSources.length > 0) {
        parentAlias = currentSources[0].alias;
      }

      // Rewire downstream steps referencing aliasToDelete to point to parentAlias
      currentSteps.forEach((step: any) => {
        if (step.type === "join") {
          if (step.left === aliasToDelete) step.left = parentAlias;
          if (step.right === aliasToDelete) step.right = parentAlias;
        } else if ("target" in step && step.target === aliasToDelete) {
          step.target = parentAlias;
        }
      });

      // Remove step
      currentSteps.splice(stepIndex, 1);

      // Rewire output_alias if needed
      let outputAlias = basePlan.output_alias;
      if (outputAlias === aliasToDelete) {
        outputAlias = currentSteps.length > 0 ? currentSteps[currentSteps.length - 1].output_alias : parentAlias;
      }

      const newPlanDraft = {
        sources: currentSources,
        steps: currentSteps,
        output_alias: outputAlias,
        summary: `Deleted step '${aliasToDelete}', rewired downstream to '${parentAlias}'.`,
      };

      setDraftPlan(newPlanDraft);
      setHasUnsavedChanges(true);

      // Clear selection or select parent node
      setSelectedNode(null);
      setNodeDataRows(null);
    } catch (err) {
      console.error("Failed to delete step:", err);
      setError(err instanceof ApiError ? err.message : "Failed to delete step");
    }
  }

  // When a user selects ANY node on the visual canvas, fetch live records and auto-scroll to profiler
  async function handleNodeSelect(node: PrepNodeData | null) {
    setSelectedNode(node);
    if (!node) {
      setNodeDataRows(null);
      return;
    }

    // Auto-scroll to preview section smoothly
    setTimeout(() => {
      previewDrawerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);

    setIsLoadingNodeData(true);
    try {
      if (node.type === "source" && selectedConnectionId) {
        const tableName = (node.details?.table as string) || node.label;
        const schemaName = (node.details?.schema as string) || undefined;
        const res = await api.sampleTable(actorEmail, selectedConnectionId, tableName, schemaName, 50);
        setNodeDataRows(res.rows);
        return;
      }

      if (currentFlow && node.alias) {
        try {
          const stepRes = await api.previewStep(actorEmail, currentFlow.id, node.alias, 50);
          if (stepRes && stepRes.rows && stepRes.rows.length > 0) {
            setNodeDataRows(stepRes.rows);
            return;
          }
        } catch (stepErr) {
          console.warn("Step preview fallback:", stepErr);
        }
      }

      const fallback = latestExecuteRun?.sample_after || latestPreviewRun?.sample_after || latestPreviewRun?.sample_before || null;
      setNodeDataRows(fallback);
    } catch (err) {
      console.error("Failed to fetch node data:", err);
      const fallback = latestExecuteRun?.sample_after || latestPreviewRun?.sample_after || null;
      setNodeDataRows(fallback);
    } finally {
      setIsLoadingNodeData(false);
    }
  }

  const activeRows = nodeDataRows || latestExecuteRun?.sample_after || latestPreviewRun?.sample_after || latestPreviewRun?.sample_before || null;

  return (
    <div className="w-full flex flex-col min-h-screen px-2 sm:px-4 py-2 space-y-3 pb-16">
      {/* Studio Header Bar */}
      <div className="w-full flex flex-wrap items-center justify-between bg-white border border-slate-200 px-4 py-2.5 rounded-lg shadow-xs gap-3 shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <span className="p-2 bg-gradient-to-tr from-blue-600 to-indigo-600 text-white rounded-lg shadow-sm">
              <Sparkles className="w-4 h-4" />
            </span>
            <div>
              <h1 className="text-sm font-bold text-slate-900 leading-tight flex items-center gap-2">
                {currentFlow ? currentFlow.name : "Tableau AI Prep Studio"}
              </h1>
              <span className="text-[11px] text-slate-500">Full-Width Visual Canvas & Smart Copilot</span>
            </div>
          </div>

          {currentFlow && <StatusBadge status={currentFlow.status} />}

          {/* Database Selector */}
          <div className="flex items-center gap-2 border-l border-slate-200 pl-4">
            <Database className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedConnectionId}
              onChange={(e) => setSelectedConnectionId(e.target.value)}
              className="text-xs bg-slate-50 border border-slate-300 rounded px-2.5 py-1 text-slate-700 font-medium focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              <option value="">Select source database...</option>
              {connections
                .filter((c) => c.type !== "tableau_server")
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.type})
                  </option>
                ))}
            </select>

            {/* Upload File Button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".csv,.xlsx,.xls,.json,.txt"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploadingFile}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded transition-colors cursor-pointer shadow-2xs"
              title="Upload CSV, Excel, or JSON as a new data source"
            >
              {isUploadingFile ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
              {isUploadingFile ? "Uploading..." : "Upload File"}
            </button>
          </div>
        </div>

        {/* Action Buttons & Copilot Toggle */}
        <div className="flex items-center gap-2">
          {/* Checkpoint Version Info & Save Button */}
          {currentFlow && (
            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg p-1">
              <button
                onClick={handleOpenHistoryModal}
                className="flex items-center gap-1 px-2 py-1 text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-200/60 rounded transition-colors cursor-pointer"
                title="View version history & restore previous checkpoints"
              >
                <History className="w-3.5 h-3.5 text-slate-500" />
                <span>{activePlan ? `v${activePlan.version_number}` : "v1"}</span>
              </button>

              <button
                onClick={() => handleSaveCheckpoint()}
                disabled={isSavingCheckpoint || (!hasUnsavedChanges && Boolean(activePlan))}
                className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded transition-all cursor-pointer shadow-2xs ${
                  hasUnsavedChanges
                    ? "bg-amber-500 hover:bg-amber-600 text-white animate-pulse"
                    : "bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 disabled:opacity-50"
                }`}
                title="Save Checkpoint (Ctrl+S / Cmd+S)"
              >
                {isSavingCheckpoint ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Save className="w-3.5 h-3.5" />
                )}
                <span>{hasUnsavedChanges ? "Save Checkpoint *" : "Saved"}</span>
              </button>
            </div>
          )}

          {/* Approve Plan Button */}
          {currentFlow && (
            <button
              onClick={handleApproveCurrentPlan}
              disabled={isApprovingPlan || currentFlow.approved_version_id === activePlan?.id}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer shadow-sm ${
                currentFlow.approved_version_id === activePlan?.id
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-300"
                  : "bg-emerald-600 hover:bg-emerald-700 text-white"
              }`}
              title="Mark this version as approved for production execution & schedules"
            >
              {isApprovingPlan ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Check className="w-3.5 h-3.5" />
              )}
              <span>
                {currentFlow.approved_version_id === activePlan?.id
                  ? "Approved (Prod)"
                  : "Approve Plan"}
              </span>
            </button>
          )}

          <button
            onClick={handleRunFlow}
            disabled={!currentFlow || isRunning || isAiGenerating}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white rounded-lg disabled:opacity-40 transition-all cursor-pointer shadow-sm"
          >
            {isRunning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            {isRunning ? "Running..." : "Run Flow"}
          </button>

          {/* Export to CSV Button */}
          <button
            onClick={() => exportToCsv(activeRows, `${currentFlow?.name || "tableau_prep_export"}.csv`)}
            disabled={!activeRows || activeRows.length === 0}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg disabled:opacity-40 transition-all cursor-pointer shadow-sm"
            title="Export output records to CSV"
          >
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </button>

          <button
            onClick={handlePublish}
            disabled={!currentFlow || isPublishing || isRunning}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-40 transition-all cursor-pointer shadow-sm"
          >
            <CloudUpload className="w-3.5 h-3.5" />
            {isPublishing ? "Publishing..." : "Publish to Tableau"}
          </button>

          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border rounded-lg transition-all cursor-pointer shadow-xs ${
              isSidebarOpen
                ? "bg-slate-800 border-slate-900 text-white"
                : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50"
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            {isSidebarOpen ? "Hide Tables" : "Show Tables"}
          </button>

          <button
            onClick={() => setIsCopilotOpen(!isCopilotOpen)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border rounded-lg transition-all cursor-pointer shadow-xs ${
              isCopilotOpen
                ? "bg-blue-50 border-blue-200 text-blue-700"
                : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            {isCopilotOpen ? "Hide Copilot" : "Show Copilot"}
          </button>
        </div>
      </div>

      {/* Alert Notices */}
      {error && (
        <div className="flex items-center gap-2 text-xs text-red-700 bg-red-50 border border-red-200 px-4 py-2.5 rounded-lg shrink-0">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {publishSuccess && (
        <div className="flex items-center gap-2 text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 px-4 py-2.5 rounded-lg shrink-0">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{publishSuccess}</span>
        </div>
      )}

      {/* Top Section: Left Tables Sidebar + Center Canvas + Collapsible Right AI Copilot */}
      <div className="grid grid-cols-12 gap-4 items-start">
        {/* Left Database Tables Sidebar */}
        {isSidebarOpen && (
          <div className="col-span-12 lg:col-span-3 xl:col-span-2 bg-white border border-slate-200 rounded-xl flex flex-col h-[486px] overflow-hidden shadow-xs">
            <div className="p-3 border-b border-slate-100 bg-slate-50/70 flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-slate-600" />
                Tables
                <span className="text-[10px] px-1.5 py-0.5 bg-slate-200/80 text-slate-700 font-semibold rounded-full">
                  {databaseTables.length}
                </span>
              </span>
              <button
                onClick={() => setIsSidebarOpen(false)}
                className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                title="Collapse Tables"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Search Input */}
            <div className="p-2.5 border-b border-slate-100 bg-white">
              <div className="relative">
                <Search className="w-3 h-3 text-slate-400 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  value={tableSearch}
                  onChange={(e) => setTableSearch(e.target.value)}
                  placeholder="Search tables..."
                  className="w-full text-[11px] bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-2.5 py-1.5 focus:outline-none focus:border-blue-500 font-medium"
                />
              </div>
            </div>

            {/* Tables List */}
            <div className="flex-1 p-2 overflow-y-auto space-y-1.5 text-xs">
              {isLoadingTables ? (
                <div className="flex flex-col items-center justify-center h-36 text-slate-400 gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-blue-500" />
                  <span className="text-[11px]">Loading schema...</span>
                </div>
              ) : databaseTables.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-36 text-center px-4 text-slate-400">
                  <Database className="w-6 h-6 mb-1.5 text-slate-300" />
                  <span className="text-[11px] font-medium text-slate-600">No tables found</span>
                  <span className="text-[10px] text-slate-400 mt-0.5">
                    {selectedConnectionId ? "Database has no accessible tables" : "Select a database connection above"}
                  </span>
                </div>
              ) : (
                databaseTables
                  .filter((t) => t.name.toLowerCase().includes(tableSearch.toLowerCase()))
                  .map((table) => {
                    const isAdded = (activePlan?.plan?.sources || []).some(
                      (s) => s.table_name === table.name
                    );
                    return (
                      <div
                        key={table.name}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData("application/tableau-table", table.name);
                          e.dataTransfer.effectAllowed = "move";
                        }}
                        className={`group p-2 rounded-lg border transition-all select-none cursor-grab active:cursor-grabbing ${
                          isAdded
                            ? "bg-blue-50/50 border-blue-200 text-blue-900"
                            : "bg-slate-50/60 hover:bg-white border-slate-200/80 hover:border-slate-300 text-slate-800"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5 overflow-hidden">
                            <Table className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                            <span className="font-semibold text-xs truncate" title={table.name}>
                              {table.name}
                            </span>
                          </div>
                          <button
                            onClick={() => handleAddTableToCanvas(table.name, table.schema || "main")}
                            className={`p-1 rounded cursor-pointer transition-colors ${
                              isAdded
                                ? "bg-blue-200/70 text-blue-800 hover:bg-blue-300"
                                : "bg-white hover:bg-blue-600 hover:text-white border border-slate-200 text-slate-600 shadow-2xs"
                            }`}
                            title={isAdded ? "Inspect table on canvas" : "Add table to canvas flow"}
                          >
                            {isAdded ? <CheckCircle2 className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                          </button>
                        </div>
                        <div className="flex items-center justify-between text-[10px] text-slate-500 mt-1 pl-5">
                          <span>{table.columns ? `${table.columns.length} columns` : "Table"}</span>
                          <span className="text-[9px] text-slate-400 group-hover:text-blue-500">drag to canvas</span>
                        </div>
                      </div>
                    );
                  })
              )}
            </div>
          </div>
        )}

        {/* Visual Graph Canvas: Responsive columns depending on Left Sidebar & Right Copilot */}
        <div
          className={`${
            isSidebarOpen && isCopilotOpen
              ? "col-span-12 lg:col-span-6 xl:col-span-7"
              : isSidebarOpen && !isCopilotOpen
              ? "col-span-12 lg:col-span-9 xl:col-span-10"
              : !isSidebarOpen && isCopilotOpen
              ? "col-span-12 lg:col-span-9 xl:col-span-9"
              : "col-span-12"
          } transition-all duration-300`}
        >
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            {displayPlan ? (
              <VisualFlowCanvas
                plan={displayPlan}
                onNodeSelect={handleNodeSelect}
                onTableDrop={(tbl) => handleAddTableToCanvas(tbl)}
                onConnectNodes={handleConnectNodes}
                onAddStepOnEdge={handleAddStepOnEdge}
                onDeleteStep={handleDeleteStep}
                className="h-[460px]"
              />
            ) : (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const tbl = e.dataTransfer.getData("application/tableau-table");
                  if (tbl) handleAddTableToCanvas(tbl);
                }}
                className="w-full h-[460px] border border-dashed border-slate-300 rounded-xl flex flex-col items-center justify-center p-8 text-center bg-slate-50/50 hover:border-blue-400 hover:bg-blue-50/20 transition-all cursor-pointer"
              >
                <div className="p-4 bg-white border border-slate-200 rounded-full shadow-xs mb-3 text-slate-400">
                  <Sparkles className="w-8 h-8 text-blue-500" />
                </div>
                <h3 className="text-base font-semibold text-slate-800">Your Visual Flow Canvas is Blank</h3>
                <p className="text-xs text-slate-500 max-w-md mt-1 leading-relaxed">
                  Drag any table from the sidebar on the left and drop it here, click <span className="font-semibold text-slate-700">+</span>, or ask the AI Prep Copilot to generate your pipeline.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right AI Copilot Panel */}
        {isCopilotOpen && (
          <div className="col-span-12 xl:col-span-4 2xl:col-span-3 bg-white border border-slate-200 rounded-xl flex flex-col h-[486px] overflow-hidden shadow-xs">
            <div className="p-3 border-b border-slate-100 bg-slate-50/70 flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <MessageSquare className="w-3.5 h-3.5 text-blue-600" /> AI Prep Copilot
              </span>
              <button
                onClick={() => setIsCopilotOpen(false)}
                className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                title="Collapse Copilot"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Chat History */}
            <div className="flex-1 p-3 overflow-y-auto space-y-3 text-xs">
              {chatMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`max-w-[92%] rounded-xl px-3 py-2 ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white shadow-xs rounded-br-none"
                        : "bg-slate-100 text-slate-800 rounded-bl-none"
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  </div>
                  <span className="text-[9px] text-slate-400 mt-1 px-1">{msg.timestamp}</span>
                </div>
              ))}
              {isAiGenerating && (
                <div className="flex items-center gap-2 text-slate-500 text-xs italic bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                  <Sparkles className="w-3.5 h-3.5 animate-spin text-blue-600" />
                  Generating visual transformation flow...
                </div>
              )}
            </div>

            {/* Prompt Input Form */}
            <form onSubmit={handleSendPrompt} className="p-3 border-t border-slate-100 bg-slate-50/60">
              <div className="relative">
                <textarea
                  value={promptInput}
                  onChange={(e) => setPromptInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendPrompt();
                    }
                  }}
                  placeholder="Ask AI Copilot: Join orders and customers, aggregate revenue by state..."
                  rows={2}
                  disabled={isAiGenerating}
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2.5 pr-10 focus:outline-none focus:border-blue-500 resize-none shadow-xs font-medium"
                />
                <button
                  type="submit"
                  disabled={!promptInput.trim() || isAiGenerating}
                  className="absolute right-2 bottom-2.5 p-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-md transition-all cursor-pointer"
                >
                  <Send className="w-3 h-3" />
                </button>
              </div>
              <span className="text-[10px] text-slate-400 block mt-1">Press Enter to generate</span>
            </form>
          </div>
        )}
      </div>

      {/* Live Data Profiler Drawer: Only appears when a node is selected, positioned with high z-index over the canvas without shifting the flow */}
      {selectedNode && (
        <div
          ref={previewDrawerRef}
          className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t-2 border-blue-500 shadow-2xl transition-all duration-300 max-h-[50vh] flex flex-col animate-in slide-in-from-bottom-5"
        >
          {/* Drawer Header */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-slate-200 bg-slate-50/90 backdrop-blur shrink-0">
            <div className="flex items-center gap-2.5">
              <span className="p-1.5 bg-blue-100 text-blue-700 rounded-md">
                <Eye className="w-4 h-4" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <span>Profile: {selectedNode.label}</span>
                  <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 uppercase">
                    {selectedNode.type}
                  </span>
                </h3>
                <p className="text-[11px] text-slate-500">
                  {selectedNode.description || selectedNode.alias} • Live Tableau distribution & sample rows
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => handleNodeSelect(null)}
                className="text-xs text-slate-600 hover:text-slate-900 flex items-center gap-1.5 cursor-pointer bg-white hover:bg-slate-100 border border-slate-300 px-3 py-1.5 rounded-lg shadow-xs font-medium"
              >
                <X className="w-3.5 h-3.5" /> Close Profile
              </button>
            </div>
          </div>

          {/* Drawer Body (Scrollable) */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {/* Step-Specific Changes Summary (Tableau Changes Log) */}
            <TableauStepChanges node={selectedNode} />

            {isLoadingNodeData ? (
              <div className="p-10 text-center text-xs text-slate-500 flex flex-col items-center justify-center gap-2.5">
                <RefreshCw className="w-5 h-5 animate-spin text-blue-600" />
                <span className="font-medium">Querying live data distributions for {selectedNode.label}...</span>
              </div>
            ) : (
              <TableauDataProfiler
                title={`Field Profile: ${selectedNode.label}`}
                rows={activeRows}
              />
            )}

            {activeRows && activeRows.length > 0 && (
              <div className="pt-3 border-t border-slate-100">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <Table className="w-3.5 h-3.5 text-blue-600" /> Sample Data Rows ({activeRows.length} Rows)
                  </h4>
                  <button
                    onClick={() => exportToCsv(activeRows, `${selectedNode?.alias || "node"}_data.csv`)}
                    className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-md transition-colors cursor-pointer shadow-2xs"
                    title="Export this step's sample rows to CSV"
                  >
                    <Download className="w-3 h-3" />
                    Download CSV
                  </button>
                </div>
                <div className="max-h-48 overflow-y-auto border border-slate-200 rounded-lg shadow-inner">
                  <DataTable rows={activeRows} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tableau Interactive Join Configuration Modal */}
      <JoinConfigModal
        isOpen={joinModalConfig.isOpen}
        onClose={() => setJoinModalConfig((prev) => ({ ...prev, isOpen: false }))}
        leftTable={joinModalConfig.leftTable}
        rightTable={joinModalConfig.rightTable}
        leftColumns={joinModalConfig.leftColumns}
        rightColumns={joinModalConfig.rightColumns}
        onConfirmJoin={handleApplyJoin}
        onConfirmUnion={handleApplyUnion}
      />

      {/* Tableau Transformation Step Action Modal (+ button on arrows) */}
      <StepActionModal
        isOpen={stepActionModal.isOpen}
        onClose={() => setStepActionModal((prev) => ({ ...prev, isOpen: false }))}
        sourceAlias={stepActionModal.sourceAlias}
        columns={stepActionModal.columns}
        onApplyStep={handleApplyCustomStep}
      />

      {/* Version History Checkpoint Modal */}
      {isHistoryModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white border border-slate-200 rounded-xl shadow-2xl w-full max-w-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-blue-600" />
                <h3 className="text-sm font-bold text-slate-800">Version History & Checkpoints</h3>
              </div>
              <button
                onClick={() => setIsHistoryModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-5 max-h-96 overflow-y-auto space-y-3">
              {versionHistory.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-xs">
                  No previous checkpoints found.
                </div>
              ) : (
                versionHistory.map((ver) => {
                  const isCurrent = activePlan?.id === ver.id;
                  const isApproved = currentFlow?.approved_version_id === ver.id;

                  return (
                    <div
                      key={ver.id}
                      className={`p-3 rounded-lg border flex items-center justify-between transition-all ${
                        isCurrent
                          ? "border-blue-300 bg-blue-50/40"
                          : "border-slate-200 bg-white hover:bg-slate-50"
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-xs text-slate-800">
                            Version {ver.version_number}
                          </span>
                          {isCurrent && (
                            <span className="text-[10px] font-semibold px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">
                              Active Editor
                            </span>
                          )}
                          {isApproved && (
                            <span className="text-[10px] font-semibold px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full flex items-center gap-1">
                              <Check className="w-3 h-3" /> Approved (Prod)
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-500">
                          {ver.change_summary || "Checkpoint snapshot"}
                        </p>
                        <span className="text-[10px] text-slate-400">
                          {new Date(ver.created_at).toLocaleString()} • {ver.source}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {!isCurrent && (
                          <button
                            onClick={() => {
                              handleRestoreVersion(ver.id);
                              setIsHistoryModalOpen(false);
                            }}
                            className="px-2.5 py-1 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors cursor-pointer"
                          >
                            Restore
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="px-5 py-3 border-t border-slate-100 bg-slate-50/50 flex justify-end">
              <button
                onClick={() => setIsHistoryModalOpen(false)}
                className="px-4 py-1.5 text-xs font-semibold bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function FlowStudioPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-400">Loading Flow Studio...</div>}>
      <FlowStudioContent />
    </Suspense>
  );
}

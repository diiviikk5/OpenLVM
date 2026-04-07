"use client";

import { useEffect, useMemo, useState } from "react";

type Workspace = { workspace_id: string; name: string };
type Collection = { collection_id: string; workspace_id: string; name: string };
type WorkspaceMember = { workspace_id: string; user_id: string; role: "viewer" | "editor" | "admin" | "owner"; created_at: string };
type Baseline = { baseline_id: string; run_id: string; label: string; created_at?: string };
type Scenario = {
  scenario_id: string;
  collection_id: string;
  name: string;
  config_path: string;
  input_text: string;
};
type Run = {
  run_id: string;
  suite_name: string;
  started_at: string;
  scenarios_executed: number;
  summary: Record<string, number>;
};
type ScenarioDiff = {
  name: string;
  baseline_status: string;
  candidate_status: string;
  baseline_score: number;
  candidate_score: number;
  warning_delta: number;
};
type Diff = {
  baseline_id?: string;
  baseline_label?: string;
  baseline_run_id: string;
  candidate_run_id: string;
  score_delta: number;
  trace_delta?: {
    baseline_trace_count: number;
    candidate_trace_count: number;
    trace_count_delta: number;
    warning_event_delta: number;
    runtime_backend_changed: boolean;
    baseline_runtime_backend: string;
    candidate_runtime_backend: string;
    chaos_targets_added: string[];
    chaos_targets_removed: string[];
  };
  scenario_diffs: ScenarioDiff[];
};
type CompareResponse = { candidate_run_id: string; diffs: Diff[] };
type CompareArtifact = {
  artifact_id: string;
  collection_id: string;
  candidate_run_id: string;
  baseline_ids: string[];
  filename: string;
  created_at: string;
  actor_id: string;
};
type RunInspection = {
  run: {
    run_id: string;
    suite_name: string;
    metadata: {
      runtime_backend?: string;
      traces?: Array<Record<string, unknown>>;
    };
    results: Array<{
      name: string;
      fork_id: number;
      fork_parent_id?: number | null;
      status: string;
      score: number;
      network_delay_ms: number;
      warnings: string[];
    }>;
  };
  trace_summary: {
    runtime_backend: string;
    trace_count: number;
    scenario_count: number;
    warning_events: number;
  };
};
type Overview = {
  workspaces: Workspace[];
  collections: Collection[];
  baselines_by_collection: Record<string, Baseline[]>;
  scenarios_by_collection: Record<string, Scenario[]>;
  compare_artifacts_by_collection: Record<string, CompareArtifact[]>;
  members_by_workspace: Record<string, WorkspaceMember[]>;
  user_role_by_workspace: Record<string, string>;
  recent_runs: Run[];
  audit_events: Array<{
    event_id: string;
    actor_id: string;
    action: string;
    entity_type: string;
    entity_id: string;
    details: Record<string, unknown>;
    created_at: string;
  }>;
};

type SessionState = {
  user_id: string;
  session_id: string;
  actor_id: string;
  authenticated: boolean;
};

const ROLE_RANK: Record<string, number> = {
  viewer: 1,
  editor: 2,
  admin: 3,
  owner: 4,
};

async function fetchOverview(): Promise<Overview> {
  const res = await fetch("/api/workbench/overview", { cache: "no-store" });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || "overview failed");
  return data;
}

async function postJson<T>(url: string, body: Record<string, unknown>, method = "POST"): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || "request failed");
  return data as T;
}

export default function WorkbenchPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [sessionState, setSessionState] = useState<SessionState | null>(null);
  const [sessionUserInput, setSessionUserInput] = useState("");

  const [selectedCollection, setSelectedCollection] = useState("");
  const [selectedRun, setSelectedRun] = useState("");
  const [selectedBaselines, setSelectedBaselines] = useState<string[]>([]);
  const [baselineSearch, setBaselineSearch] = useState("");
  const [baselineSort, setBaselineSort] = useState<"newest" | "oldest" | "label">("newest");
  const [isRunning, setIsRunning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [lastRunId, setLastRunId] = useState("");
  const [compare, setCompare] = useState<CompareResponse | null>(null);
  const [isSavingArtifact, setIsSavingArtifact] = useState(false);
  const [runInspection, setRunInspection] = useState<RunInspection | null>(null);
  const [runFilterScenario, setRunFilterScenario] = useState("all");
  const [runFilterStatus, setRunFilterStatus] = useState("all");
  const [runFilterFork, setRunFilterFork] = useState("");
  const [traceFilterScenario, setTraceFilterScenario] = useState("all");
  const [traceFilterFork, setTraceFilterFork] = useState("");
  const [selectedTraceKey, setSelectedTraceKey] = useState("");
  const [pruneKeepLatest, setPruneKeepLatest] = useState("10");
  const [quickPrompt, setQuickPrompt] = useState("");
  const [quickConfigPath, setQuickConfigPath] = useState("examples/swarm.yaml");
  const [quickRunning, setQuickRunning] = useState(false);
  const [quickLastRun, setQuickLastRun] = useState<Run | null>(null);

  const [workspaceName, setWorkspaceName] = useState("");
  const [collectionWorkspace, setCollectionWorkspace] = useState("");
  const [collectionName, setCollectionName] = useState("");
  const [memberWorkspace, setMemberWorkspace] = useState("");
  const [memberUserId, setMemberUserId] = useState("");
  const [memberRole, setMemberRole] = useState<"viewer" | "editor" | "admin">("viewer");

  const [scenarioEditId, setScenarioEditId] = useState("");
  const [scenarioCollection, setScenarioCollection] = useState("");
  const [scenarioName, setScenarioName] = useState("");
  const [scenarioConfig, setScenarioConfig] = useState("examples/swarm.yaml");
  const [scenarioInput, setScenarioInput] = useState("");

  const [baselineRun, setBaselineRun] = useState("");
  const [baselineLabel, setBaselineLabel] = useState("stable");

  const load = async () => {
    const data = await fetchOverview();
    setOverview(data);
    if (data.workspaces[0] && !collectionWorkspace) setCollectionWorkspace(data.workspaces[0].workspace_id);
    if (data.workspaces[0] && !memberWorkspace) setMemberWorkspace(data.workspaces[0].workspace_id);
    if (data.collections[0] && !selectedCollection) {
      const col = data.collections[0].collection_id;
      setSelectedCollection(col);
      setScenarioCollection(col);
      const bases = data.baselines_by_collection[col] || [];
      if (bases[0]) setSelectedBaselines([bases[0].baseline_id]);
    }
    if (data.recent_runs[0] && !selectedRun) {
      setSelectedRun(data.recent_runs[0].run_id);
      setBaselineRun(data.recent_runs[0].run_id);
    }
  };

  useEffect(() => {
    void (async () => {
      try {
        const sessionRes = await fetch("/api/workbench/session", { cache: "no-store" });
        const sessionData = (await sessionRes.json()) as SessionState;
        let effectiveSession = sessionData;
        if (!sessionData.authenticated || sessionData.user_id === "anonymous") {
          const created = await postJson<SessionState>("/api/workbench/session", {});
          effectiveSession = created;
        }
        setSessionState(effectiveSession);

        const data = await fetchOverview();
        setOverview(data);
        if (data.workspaces[0]) {
          setCollectionWorkspace(data.workspaces[0].workspace_id);
          setMemberWorkspace(data.workspaces[0].workspace_id);
        }
        if (data.collections[0]) {
          const col = data.collections[0].collection_id;
          setSelectedCollection(col);
          setScenarioCollection(col);
          const bases = data.baselines_by_collection[col] || [];
          if (bases[0]) setSelectedBaselines([bases[0].baseline_id]);
        }
        if (data.recent_runs[0]) {
          setSelectedRun(data.recent_runs[0].run_id);
          setBaselineRun(data.recent_runs[0].run_id);
        }
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  const baselines = useMemo(
    () => (overview && selectedCollection ? overview.baselines_by_collection[selectedCollection] || [] : []),
    [overview, selectedCollection]
  );
  const filteredBaselines = useMemo(() => {
    const search = baselineSearch.trim().toLowerCase();
    const rows = [...baselines].filter((row) => {
      if (!search) return true;
      return row.label.toLowerCase().includes(search) || row.run_id.toLowerCase().includes(search);
    });
    rows.sort((a, b) => {
      if (baselineSort === "label") return a.label.localeCompare(b.label);
      const aTime = new Date(a.created_at || 0).getTime();
      const bTime = new Date(b.created_at || 0).getTime();
      if (baselineSort === "oldest") return aTime - bTime;
      return bTime - aTime;
    });
    return rows;
  }, [baselines, baselineSearch, baselineSort]);
  const scenarios = useMemo(
    () => (overview && selectedCollection ? overview.scenarios_by_collection[selectedCollection] || [] : []),
    [overview, selectedCollection]
  );
  const compareArtifacts = useMemo(
    () => (overview && selectedCollection ? overview.compare_artifacts_by_collection[selectedCollection] || [] : []),
    [overview, selectedCollection]
  );

  const workspaceNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const ws of overview?.workspaces || []) map[ws.workspace_id] = ws.name;
    return map;
  }, [overview]);
  const collectionWorkspaceMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const col of overview?.collections || []) map[col.collection_id] = col.workspace_id;
    return map;
  }, [overview]);
  const effectiveRoleByWorkspace = useMemo(() => {
    const map: Record<string, string> = {};
    for (const ws of overview?.workspaces || []) {
      const explicitRole = overview?.user_role_by_workspace?.[ws.workspace_id] || "";
      const members = overview?.members_by_workspace?.[ws.workspace_id] || [];
      map[ws.workspace_id] = explicitRole || (members.length === 0 ? "owner" : "");
    }
    return map;
  }, [overview]);
  const canInWorkspace = (workspaceId: string, minRole: "viewer" | "editor" | "admin" | "owner") => {
    const role = effectiveRoleByWorkspace[workspaceId] || "";
    return (ROLE_RANK[role] || 0) >= ROLE_RANK[minRole];
  };
  const currentWorkspaceRole = useMemo(() => {
    if (!memberWorkspace) return "";
    return effectiveRoleByWorkspace[memberWorkspace] || "";
  }, [effectiveRoleByWorkspace, memberWorkspace]);
  const selectedWorkspaceMembers = useMemo(() => {
    if (!overview || !memberWorkspace) return [];
    return overview.members_by_workspace[memberWorkspace] || [];
  }, [overview, memberWorkspace]);
  const selectedCollectionWorkspaceId = collectionWorkspaceMap[selectedCollection] || "";
  const canEditSelectedCollection = selectedCollectionWorkspaceId ? canInWorkspace(selectedCollectionWorkspaceId, "editor") : false;
  const canAdminSelectedCollection = selectedCollectionWorkspaceId ? canInWorkspace(selectedCollectionWorkspaceId, "admin") : false;
  const canViewSelectedCollection = selectedCollectionWorkspaceId ? canInWorkspace(selectedCollectionWorkspaceId, "viewer") : false;
  const canManageSelectedWorkspace = memberWorkspace ? canInWorkspace(memberWorkspace, "admin") : false;
  const scenarioCollectionWorkspaceId = collectionWorkspaceMap[scenarioCollection] || "";
  const canEditScenarioCollection = scenarioCollectionWorkspaceId ? canInWorkspace(scenarioCollectionWorkspaceId, "editor") : false;

  const toggleBaseline = (id: string) =>
    setSelectedBaselines((arr) => (arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id]));
  const selectLatestBaselines = (count: number) => {
    const ids = [...baselines]
      .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
      .slice(0, count)
      .map((b) => b.baseline_id);
    setSelectedBaselines(ids);
  };

  const setEditing = (s: Scenario) => {
    setScenarioEditId(s.scenario_id);
    setScenarioCollection(s.collection_id);
    setScenarioName(s.name);
    setScenarioConfig(s.config_path);
    setScenarioInput(s.input_text);
  };

  const ensureQuickCollection = async (): Promise<string> => {
    if (selectedCollection) return selectedCollection;
    const current = await fetchOverview();
    let workspaceId = current.workspaces[0]?.workspace_id;
    if (!workspaceId) {
      const created = await postJson<Workspace>("/api/workbench/workspace", {
        name: "Quick Workspace",
      });
      workspaceId = created.workspace_id;
    }
    const existingQuick = current.collections.find((c) => c.workspace_id === workspaceId);
    let collectionId = existingQuick?.collection_id;
    if (!collectionId) {
      const createdCollection = await postJson<Collection>("/api/workbench/collection", {
        workspace_id: workspaceId,
        name: "Quick Collection",
      });
      collectionId = createdCollection.collection_id;
    }
    setCollectionWorkspace(workspaceId);
    setSelectedCollection(collectionId);
    setScenarioCollection(collectionId);
    return collectionId;
  };

  const runQuickTest = async () => {
    if (!quickPrompt.trim()) {
      setError("Enter a prompt first");
      return;
    }
    setQuickRunning(true);
    try {
      const collectionId = await ensureQuickCollection();
      const scenarioName = `quick-${Date.now()}`;
      await postJson("/api/workbench/scenario", {
        collection_id: collectionId,
        name: scenarioName,
        config_path: quickConfigPath,
        input_text: quickPrompt.trim(),
      });
      const run = await postJson<Run>("/api/workbench/run", { collection_id: collectionId });
      setQuickLastRun(run);
      setSelectedRun(run.run_id);
      setBaselineRun(run.run_id);
      setLastRunId(run.run_id);
      setQuickPrompt("");
      await load();
      setMsg(`Quick run complete: ${run.run_id}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setQuickRunning(false);
    }
  };

  useEffect(() => {
    if (!selectedRun) return;
    void (async () => {
      try {
        const res = await fetch(`/api/workbench/run?run_id=${encodeURIComponent(selectedRun)}`, { cache: "no-store" });
        const data = (await res.json()) as RunInspection | { error?: string };
        if (!res.ok || ("error" in data && data.error)) {
          throw new Error(("error" in data ? data.error : undefined) || "run inspection failed");
        }
        setRunInspection(data as RunInspection);
      } catch {
        setRunInspection(null);
      }
    })();
  }, [selectedRun]);

  const runInspectionScenarioOptions = useMemo(() => {
    const options = new Set<string>();
    for (const row of runInspection?.run.results || []) options.add(row.name);
    return ["all", ...Array.from(options)];
  }, [runInspection]);

  const runInspectionRows = useMemo(() => {
    const rows = runInspection?.run.results || [];
    const forkFilter = runFilterFork.trim();
    return rows.filter((row) => {
      if (runFilterScenario !== "all" && row.name !== runFilterScenario) return false;
      if (runFilterStatus !== "all" && row.status !== runFilterStatus) return false;
      if (forkFilter && String(row.fork_id) !== forkFilter) return false;
      return true;
    });
  }, [runInspection, runFilterScenario, runFilterStatus, runFilterFork]);

  const traceRows = useMemo(() => {
    const traces = (runInspection?.run.metadata.traces || []) as Array<Record<string, unknown>>;
    return traces.map((trace, index) => {
      const forkId = Number(trace.fork_handle ?? trace.fork_id ?? 0);
      const scenarioName = String(trace.scenario_name || "unknown");
      const key = `${forkId || index}-${scenarioName}-${index}`;
      return { key, trace, forkId, scenarioName };
    });
  }, [runInspection]);

  const traceScenarioOptions = useMemo(() => {
    const values = new Set<string>();
    for (const row of traceRows) values.add(row.scenarioName);
    return ["all", ...Array.from(values)];
  }, [traceRows]);

  const filteredTraceRows = useMemo(() => {
    const forkFilter = traceFilterFork.trim();
    return traceRows.filter((row) => {
      if (traceFilterScenario !== "all" && row.scenarioName !== traceFilterScenario) return false;
      if (forkFilter && String(row.forkId) !== forkFilter) return false;
      return true;
    });
  }, [traceRows, traceFilterScenario, traceFilterFork]);

  const selectedTrace = useMemo(() => {
    return filteredTraceRows.find((row) => row.key === selectedTraceKey) || filteredTraceRows[0] || null;
  }, [filteredTraceRows, selectedTraceKey]);

  useEffect(() => {
    if (!filteredTraceRows.length) {
      setSelectedTraceKey("");
      return;
    }
    if (!filteredTraceRows.some((row) => row.key === selectedTraceKey)) {
      setSelectedTraceKey(filteredTraceRows[0].key);
    }
  }, [filteredTraceRows, selectedTraceKey]);

  const downloadText = (filename: string, content: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const exportCompareJson = () => {
    if (!compare) return;
    const exportMeta = {
      export_version: "openlvm.compare.v1",
      exported_at: new Date().toISOString(),
      collection_id: selectedCollection,
      candidate_run_id: compare.candidate_run_id,
      selected_baseline_ids: selectedBaselines,
      baseline_count: compare.diffs.length,
    };
    const payload = { metadata: exportMeta, compare };
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const candidate = compare.candidate_run_id.replace(/[^a-zA-Z0-9_-]/g, "_");
    downloadText(`openlvm-compare-${candidate}-${stamp}.json`, JSON.stringify(payload, null, 2), "application/json");
  };

  const exportCompareCsv = () => {
    if (!compare) return;
    const header = [
      "baseline_id",
      "baseline_label",
      "baseline_run_id",
      "candidate_run_id",
      "export_version",
      "exported_at",
      "collection_id",
      "scenario_name",
      "baseline_status",
      "candidate_status",
      "baseline_score",
      "candidate_score",
      "warning_delta",
      "trace_count_delta",
      "warning_event_delta",
      "baseline_backend",
      "candidate_backend",
      "chaos_targets_added",
      "chaos_targets_removed",
    ];
    const escapeCsv = (value: unknown) => `"${String(value ?? "").replace(/"/g, "\"\"")}"`;
    const lines = [header.map(escapeCsv).join(",")];
    const exportVersion = "openlvm.compare.v1";
    const exportedAt = new Date().toISOString();
    for (const diff of compare.diffs) {
      for (const scenario of diff.scenario_diffs) {
        lines.push(
          [
            diff.baseline_id || "",
            diff.baseline_label || "",
            diff.baseline_run_id,
            diff.candidate_run_id,
            exportVersion,
            exportedAt,
            selectedCollection,
            scenario.name,
            scenario.baseline_status,
            scenario.candidate_status,
            scenario.baseline_score,
            scenario.candidate_score,
            scenario.warning_delta,
            diff.trace_delta?.trace_count_delta ?? "",
            diff.trace_delta?.warning_event_delta ?? "",
            diff.trace_delta?.baseline_runtime_backend ?? "",
            diff.trace_delta?.candidate_runtime_backend ?? "",
            (diff.trace_delta?.chaos_targets_added || []).join("|"),
            (diff.trace_delta?.chaos_targets_removed || []).join("|"),
          ]
            .map(escapeCsv)
            .join(",")
        );
      }
    }
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const candidate = compare.candidate_run_id.replace(/[^a-zA-Z0-9_-]/g, "_");
    downloadText(`openlvm-compare-${candidate}-${stamp}.csv`, lines.join("\n"), "text/csv");
  };

  const saveCompareArtifact = async () => {
    if (!compare || !selectedCollection || !selectedRun) return;
    setIsSavingArtifact(true);
    try {
      const result = await postJson<{ artifact_id: string; filename: string }>("/api/workbench/artifact", {
        collection_id: selectedCollection,
        run_id: selectedRun,
        baseline_ids: selectedBaselines,
      });
      await load();
      setMsg(`Artifact saved: ${result.filename}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setIsSavingArtifact(false);
    }
  };

  const downloadSavedArtifact = async (artifactId: string, format: "json" | "csv") => {
    try {
      const res = await fetch(`/api/workbench/artifact?artifact_id=${encodeURIComponent(artifactId)}&format=${format}`, { cache: "no-store" });
      const data = (await res.json()) as { filename: string; content: string; mime_type: string; error?: string };
      if (!res.ok || data.error) throw new Error(data.error || "artifact download failed");
      downloadText(data.filename, data.content, data.mime_type);
    } catch (e) {
      setError(String(e));
    }
  };

  const deleteSavedArtifact = async (artifactId: string) => {
    try {
      await postJson<{ deleted: boolean }>("/api/workbench/artifact", { artifact_id: artifactId }, "DELETE");
      await load();
      setMsg("Artifact deleted");
    } catch (e) {
      setError(String(e));
    }
  };

  const pruneSavedArtifacts = async () => {
    if (!selectedCollection) return;
    const keepLatest = Number(pruneKeepLatest);
    if (Number.isNaN(keepLatest) || keepLatest < 0) {
      setError("keep_latest must be >= 0");
      return;
    }
    try {
      const result = await postJson<{ deleted_count: number; keep_latest: number }>(
        "/api/workbench/artifact",
        { collection_id: selectedCollection, keep_latest: keepLatest },
        "DELETE"
      );
      await load();
      setMsg(`Artifacts pruned: deleted ${result.deleted_count}, kept ${result.keep_latest}`);
    } catch (e) {
      setError(String(e));
    }
  };

  const replayFromArtifact = async (artifactId: string) => {
    try {
      const res = await fetch(`/api/workbench/artifact?artifact_id=${encodeURIComponent(artifactId)}&format=json`, { cache: "no-store" });
      const data = (await res.json()) as {
        candidate_run_id?: string;
        baseline_ids?: string[];
        error?: string;
      };
      if (!res.ok || data.error || !data.candidate_run_id) {
        throw new Error(data.error || "artifact replay failed");
      }
      setSelectedRun(data.candidate_run_id);
      setSelectedBaselines(data.baseline_ids || []);
      const resp = await postJson<CompareResponse>("/api/workbench/compare", {
        collection_id: selectedCollection,
        run_id: data.candidate_run_id,
        baseline_ids: data.baseline_ids || [],
      });
      setCompare(resp);
      setMsg(`Replayed compare from artifact ${artifactId}`);
    } catch (e) {
      setError(String(e));
    }
  };

  const switchSessionUser = async () => {
    const nextUser = sessionUserInput.trim();
    if (!nextUser) {
      setError("Enter a user id to switch session");
      return;
    }
    try {
      const created = await postJson<SessionState>("/api/workbench/session", { user_id: nextUser });
      setSessionState(created);
      setSessionUserInput("");
      await load();
      setMsg(`Session switched to ${created.user_id}`);
    } catch (e) {
      setError(String(e));
    }
  };

  const clearSession = async () => {
    try {
      const res = await fetch("/api/workbench/session", { method: "DELETE" });
      const data = (await res.json()) as { cleared?: boolean; error?: string };
      if (!res.ok || data.error) throw new Error(data.error || "failed to clear session");
      const created = await postJson<SessionState>("/api/workbench/session", {});
      setSessionState(created);
      await load();
      setMsg("Session cleared and reinitialized");
    } catch (e) {
      setError(String(e));
    }
  };

  const upsertMember = async () => {
    const userId = memberUserId.trim();
    if (!memberWorkspace || !userId) {
      setError("Choose workspace and user id");
      return;
    }
    try {
      await postJson("/api/workbench/member", {
        workspace_id: memberWorkspace,
        user_id: userId,
        role: memberRole,
      });
      setMemberUserId("");
      await load();
      setMsg(`Member saved: ${userId} (${memberRole})`);
    } catch (e) {
      setError(String(e));
    }
  };

  const removeMember = async (workspaceId: string, userId: string) => {
    try {
      await postJson("/api/workbench/member", {
        workspace_id: workspaceId,
        user_id: userId,
      }, "DELETE");
      await load();
      setMsg(`Member removed: ${userId}`);
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <main className="min-h-screen bg-near-black text-ivory p-6">
      <h1 className="text-3xl mb-3">OpenLVM Workbench</h1>
      {sessionState && (
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-warm-silver">
          <span>session {sessionState.user_id} / {sessionState.session_id}</span>
          <input
            className="bg-dark-surface p-1.5 rounded text-xs"
            placeholder="switch user id"
            value={sessionUserInput}
            onChange={(e) => setSessionUserInput(e.target.value)}
          />
          <button className="border border-border-dark px-2 py-1 rounded text-xs" onClick={() => void switchSessionUser()}>
            Switch User
          </button>
          <button className="border border-border-dark px-2 py-1 rounded text-xs" onClick={() => void clearSession()}>
            Reset Session
          </button>
        </div>
      )}
      {error && <p className="text-coral mb-3">{error}</p>}
      {msg && <p className="text-accent-emerald mb-3">{msg}</p>}

      <section className="border border-border-dark rounded-xl p-4 mb-4">
        <div className="flex items-center justify-between gap-2 mb-2">
          <h2 className="text-xl">Quick Run</h2>
          <button className="border border-border-dark px-3 py-1 rounded text-sm" onClick={() => setShowAdvanced((v) => !v)}>
            {showAdvanced ? "Hide Advanced" : "Show Advanced"}
          </button>
        </div>
        <p className="text-sm text-warm-silver mb-2">Paste one test input and run. Workspace/collection setup is handled automatically if missing.</p>
        <div className="grid gap-2 md:grid-cols-4">
          <input
            className="bg-dark-surface p-2 rounded md:col-span-3"
            placeholder="Test prompt (e.g. Cancel my subscription)"
            value={quickPrompt}
            onChange={(e) => setQuickPrompt(e.target.value)}
          />
          <input
            className="bg-dark-surface p-2 rounded"
            placeholder="Config path"
            value={quickConfigPath}
            onChange={(e) => setQuickConfigPath(e.target.value)}
          />
        </div>
        <div className="mt-2 flex gap-2">
          <button className="bg-terracotta px-3 py-1 rounded" disabled={quickRunning} onClick={() => void runQuickTest()}>
            {quickRunning ? "Running..." : "Run Quick Test"}
          </button>
          {quickLastRun && (
            <button
              className="border border-border-dark px-3 py-1 rounded disabled:opacity-50"
              disabled={!canEditSelectedCollection}
              onClick={async () => {
                try {
                  await postJson("/api/workbench/baseline", {
                    collection_id: selectedCollection,
                    run_id: quickLastRun.run_id,
                    label: `quick-${new Date().toISOString().slice(0, 19)}`,
                  });
                  await load();
                  setMsg("Quick baseline saved");
                } catch (e) {
                  setError(String(e));
                }
              }}
            >
              Save Quick Baseline
            </button>
          )}
        </div>
        {quickLastRun && (
          <p className="mt-2 text-sm text-warm-silver">
            last quick run: {quickLastRun.run_id} | scenarios {quickLastRun.scenarios_executed} | passed {quickLastRun.summary.passed ?? 0} | warnings {quickLastRun.summary.warnings ?? 0}
          </p>
        )}
      </section>

      {showAdvanced && (
      <>
      <div className="grid gap-4 md:grid-cols-2">
        <section className="border border-border-dark rounded-xl p-4">
          <h2 className="text-xl mb-2">Setup</h2>
          <div className="space-y-2">
            <input className="w-full bg-dark-surface p-2 rounded" placeholder="Workspace name" value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)} />
            <button className="bg-terracotta px-3 py-1 rounded" onClick={async () => { try { await postJson("/api/workbench/workspace", { name: workspaceName }); setWorkspaceName(""); await load(); setMsg("Workspace created"); } catch (e) { setError(String(e)); } }}>Create Workspace</button>
            <button className="border border-border-dark px-3 py-1 rounded disabled:opacity-50" disabled={!collectionWorkspace || !canInWorkspace(collectionWorkspace, "admin")} onClick={async () => { try { if (!collectionWorkspace || !workspaceName) return; await postJson("/api/workbench/workspace", { workspace_id: collectionWorkspace, name: workspaceName }, "PATCH"); setWorkspaceName(""); await load(); setMsg("Workspace updated"); } catch (e) { setError(String(e)); } }}>Update Selected Workspace</button>
            <button className="border border-coral px-3 py-1 rounded text-coral disabled:opacity-50" disabled={!collectionWorkspace || !canInWorkspace(collectionWorkspace, "owner")} onClick={async () => { try { if (!collectionWorkspace) return; await postJson("/api/workbench/workspace", { workspace_id: collectionWorkspace }, "DELETE"); await load(); setMsg("Workspace deleted"); } catch (e) { setError(String(e)); } }}>Delete Selected Workspace</button>
            <select className="w-full bg-dark-surface p-2 rounded" value={collectionWorkspace} onChange={(e) => setCollectionWorkspace(e.target.value)}>
              {(overview?.workspaces || []).map((w) => <option key={w.workspace_id} value={w.workspace_id}>{w.name}</option>)}
            </select>
            <input className="w-full bg-dark-surface p-2 rounded" placeholder="Collection name" value={collectionName} onChange={(e) => setCollectionName(e.target.value)} />
            <button className="bg-terracotta px-3 py-1 rounded disabled:opacity-50" disabled={!collectionWorkspace || !canInWorkspace(collectionWorkspace, "editor")} onClick={async () => { try { const c = await postJson<Collection>("/api/workbench/collection", { workspace_id: collectionWorkspace, name: collectionName }); setCollectionName(""); setSelectedCollection(c.collection_id); setScenarioCollection(c.collection_id); await load(); setMsg("Collection created"); } catch (e) { setError(String(e)); } }}>Create Collection</button>
            <button className="border border-border-dark px-3 py-1 rounded disabled:opacity-50" disabled={!canEditSelectedCollection} onClick={async () => { try { if (!selectedCollection || !collectionName) return; await postJson("/api/workbench/collection", { collection_id: selectedCollection, name: collectionName }, "PATCH"); setCollectionName(""); await load(); setMsg("Collection updated"); } catch (e) { setError(String(e)); } }}>Update Selected Collection</button>
            <button className="border border-coral px-3 py-1 rounded text-coral disabled:opacity-50" disabled={!canAdminSelectedCollection} onClick={async () => { try { if (!selectedCollection) return; await postJson("/api/workbench/collection", { collection_id: selectedCollection }, "DELETE"); await load(); setMsg("Collection deleted"); } catch (e) { setError(String(e)); } }}>Delete Selected Collection</button>
          </div>
        </section>

        <section className="border border-border-dark rounded-xl p-4">
          <h2 className="text-xl mb-2">{scenarioEditId ? "Edit Scenario" : "Save Scenario"}</h2>
          <div className="space-y-2">
            <select className="w-full bg-dark-surface p-2 rounded" value={scenarioCollection} onChange={(e) => setScenarioCollection(e.target.value)}>
              {(overview?.collections || []).map((c) => <option key={c.collection_id} value={c.collection_id}>{c.name}</option>)}
            </select>
            <input className="w-full bg-dark-surface p-2 rounded" placeholder="Scenario name" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} />
            <input className="w-full bg-dark-surface p-2 rounded" placeholder="Config path" value={scenarioConfig} onChange={(e) => setScenarioConfig(e.target.value)} />
            <textarea className="w-full bg-dark-surface p-2 rounded" placeholder="Input" value={scenarioInput} onChange={(e) => setScenarioInput(e.target.value)} />
            <div className="flex gap-2">
              <button className="bg-terracotta px-3 py-1 rounded disabled:opacity-50" disabled={!canEditScenarioCollection} onClick={async () => { try { if (scenarioEditId) { await postJson("/api/workbench/scenario", { scenario_id: scenarioEditId, name: scenarioName, config_path: scenarioConfig, input_text: scenarioInput }, "PATCH"); } else { await postJson("/api/workbench/scenario", { collection_id: scenarioCollection, name: scenarioName, config_path: scenarioConfig, input_text: scenarioInput }); } setScenarioEditId(""); setScenarioName(""); setScenarioInput(""); setScenarioConfig("examples/swarm.yaml"); await load(); setMsg("Scenario saved"); } catch (e) { setError(String(e)); } }}>{scenarioEditId ? "Update" : "Save"}</button>
              {scenarioEditId && <button className="border border-border-dark px-3 py-1 rounded" onClick={() => { setScenarioEditId(""); setScenarioName(""); setScenarioInput(""); setScenarioConfig("examples/swarm.yaml"); }}>Cancel</button>}
            </div>
          </div>
        </section>
      </div>

      <section className="border border-border-dark rounded-xl p-4 mt-4">
        <h2 className="text-xl mb-2">Workspace Members</h2>
        <div className="grid gap-2 md:grid-cols-4 mb-3">
          <select className="bg-dark-surface p-2 rounded" value={memberWorkspace} onChange={(e) => setMemberWorkspace(e.target.value)}>
            {(overview?.workspaces || []).map((w) => <option key={w.workspace_id} value={w.workspace_id}>{w.name}</option>)}
          </select>
          <input
            className="bg-dark-surface p-2 rounded"
            placeholder="user id"
            value={memberUserId}
            onChange={(e) => setMemberUserId(e.target.value)}
          />
          <select className="bg-dark-surface p-2 rounded" value={memberRole} onChange={(e) => setMemberRole(e.target.value as "viewer" | "editor" | "admin")}>
            <option value="viewer">viewer</option>
            <option value="editor">editor</option>
            <option value="admin">admin</option>
          </select>
          <button className="bg-terracotta px-3 py-1 rounded disabled:opacity-50" disabled={!canManageSelectedWorkspace} onClick={() => void upsertMember()}>Add / Update Member</button>
        </div>
        <p className="text-xs text-warm-silver mb-2">Your role in selected workspace: {currentWorkspaceRole || "none"}</p>
        <div className="space-y-2">
          {selectedWorkspaceMembers.map((member) => (
            <div key={`${member.workspace_id}-${member.user_id}`} className="flex items-center justify-between border border-border-dark rounded p-2 text-sm">
              <span>{member.user_id} ({member.role})</span>
              <button
                className="border border-coral px-2 py-1 rounded text-coral"
                disabled={member.role === "owner" || !canManageSelectedWorkspace}
                onClick={() => void removeMember(member.workspace_id, member.user_id)}
              >
                Remove
              </button>
            </div>
          ))}
          {selectedWorkspaceMembers.length === 0 && <p className="text-warm-silver">No explicit members yet (legacy public workspace).</p>}
        </div>
      </section>

      <section className="border border-border-dark rounded-xl p-4 mt-4">
        <h2 className="text-xl mb-2">Scenarios for Selected Collection</h2>
        <select className="w-full bg-dark-surface p-2 rounded mb-2" value={selectedCollection} onChange={(e) => setSelectedCollection(e.target.value)}>
          {(overview?.collections || []).map((c) => <option key={c.collection_id} value={c.collection_id}>{c.name} ({workspaceNames[c.workspace_id] || c.workspace_id})</option>)}
        </select>
        <div className="space-y-2">
          {scenarios.map((s) => (
            <div key={s.scenario_id} className="flex items-center justify-between border border-border-dark rounded p-2">
              <div>{s.name}</div>
              <div className="flex gap-2">
                <button className="border border-border-dark px-2 py-1 rounded" onClick={() => setEditing(s)}>Edit</button>
                <button className="border border-coral px-2 py-1 rounded text-coral disabled:opacity-50" disabled={!canEditSelectedCollection} onClick={async () => { try { await postJson("/api/workbench/scenario", { scenario_id: s.scenario_id }, "DELETE"); await load(); setMsg("Scenario deleted"); } catch (e) { setError(String(e)); } }}>Delete</button>
              </div>
            </div>
          ))}
          {scenarios.length === 0 && <p className="text-warm-silver">No scenarios yet.</p>}
        </div>
      </section>
      </>
      )}

      <section className="border border-border-dark rounded-xl p-4 mt-4">
        <h2 className="text-xl mb-2">Run and Compare</h2>
        <div className="grid gap-2 md:grid-cols-3">
          <select className="bg-dark-surface p-2 rounded" value={selectedCollection} onChange={(e) => setSelectedCollection(e.target.value)}>
            {(overview?.collections || []).map((c) => <option key={c.collection_id} value={c.collection_id}>{c.name}</option>)}
          </select>
          <select className="bg-dark-surface p-2 rounded" value={selectedRun} onChange={(e) => setSelectedRun(e.target.value)}>
            {(overview?.recent_runs || []).map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id}</option>)}
          </select>
          <button className="bg-terracotta px-3 py-1 rounded disabled:opacity-50" disabled={isRunning || !canEditSelectedCollection} onClick={async () => { try { setIsRunning(true); const run = await postJson<Run>("/api/workbench/run", { collection_id: selectedCollection }); setLastRunId(run.run_id); setSelectedRun(run.run_id); setBaselineRun(run.run_id); await load(); setMsg(`Run complete: ${run.run_id}`); } catch (e) { setError(String(e)); } finally { setIsRunning(false); } }}>{isRunning ? "Running..." : "Run Collection"}</button>
        </div>
        <div className="mt-2 p-2 border border-border-dark rounded">
          <p className="text-sm text-warm-silver mb-1">Choose baseline(s)</p>
          <div className="grid gap-2 md:grid-cols-3 mb-2">
            <input
              className="bg-dark-surface p-2 rounded text-sm"
              placeholder="Search baseline label/run"
              value={baselineSearch}
              onChange={(e) => setBaselineSearch(e.target.value)}
            />
            <select
              className="bg-dark-surface p-2 rounded text-sm"
              value={baselineSort}
              onChange={(e) => setBaselineSort(e.target.value as "newest" | "oldest" | "label")}
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="label">Label A-Z</option>
            </select>
            <div className="flex gap-2">
              <button className="border border-border-dark px-2 py-1 rounded text-xs" onClick={() => setSelectedBaselines(filteredBaselines.map((b) => b.baseline_id))}>All</button>
              <button className="border border-border-dark px-2 py-1 rounded text-xs" onClick={() => setSelectedBaselines([])}>None</button>
              <button className="border border-border-dark px-2 py-1 rounded text-xs" onClick={() => selectLatestBaselines(2)}>Latest 2</button>
              <button className="border border-border-dark px-2 py-1 rounded text-xs" onClick={() => selectLatestBaselines(3)}>Latest 3</button>
            </div>
          </div>
          {filteredBaselines.map((b) => (
            <label key={b.baseline_id} className="block text-sm">
              <input type="checkbox" checked={selectedBaselines.includes(b.baseline_id)} onChange={() => toggleBaseline(b.baseline_id)} /> {b.label} ({b.run_id})
            </label>
          ))}
          {filteredBaselines.length === 0 && <p className="text-sm text-warm-silver">No baselines match current filters.</p>}
        </div>
        <div className="mt-2 flex gap-2">
          <input className="bg-dark-surface p-2 rounded flex-1" placeholder="Baseline run id" value={baselineRun} onChange={(e) => setBaselineRun(e.target.value)} />
          <input className="bg-dark-surface p-2 rounded w-40" placeholder="Label" value={baselineLabel} onChange={(e) => setBaselineLabel(e.target.value)} />
          <button className="border border-border-dark px-3 py-1 rounded disabled:opacity-50" disabled={!canEditSelectedCollection} onClick={async () => { try { await postJson("/api/workbench/baseline", { collection_id: selectedCollection, run_id: baselineRun, label: baselineLabel }); await load(); setMsg("Baseline saved"); } catch (e) { setError(String(e)); } }}>Save Baseline</button>
          <button className="bg-terracotta px-3 py-1 rounded disabled:opacity-50" disabled={isComparing || !canViewSelectedCollection} onClick={async () => { try { setIsComparing(true); const resp = await postJson<CompareResponse>("/api/workbench/compare", { collection_id: selectedCollection, run_id: selectedRun, baseline_ids: selectedBaselines }); setCompare(resp); setMsg(`Compared ${resp.diffs.length} baseline(s)`); } catch (e) { setError(String(e)); } finally { setIsComparing(false); } }}>{isComparing ? "Comparing..." : "Compare"}</button>
        </div>
        {lastRunId && <p className="mt-2 text-sm text-accent-emerald">Latest run: {lastRunId}</p>}
      </section>

      {runInspection && (
        <section className="border border-border-dark rounded-xl p-4 mt-4">
          <h2 className="text-xl mb-2">Run Inspection</h2>
          <p className="text-sm text-warm-silver">
            {runInspection.run.run_id} | backend {runInspection.trace_summary.runtime_backend} | traces {runInspection.trace_summary.trace_count} | warnings {runInspection.trace_summary.warning_events}
          </p>
          <div className="mt-2 grid gap-2 md:grid-cols-4">
            <select className="bg-dark-surface p-2 rounded text-sm" value={runFilterScenario} onChange={(e) => setRunFilterScenario(e.target.value)}>
              {runInspectionScenarioOptions.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
            <select className="bg-dark-surface p-2 rounded text-sm" value={runFilterStatus} onChange={(e) => setRunFilterStatus(e.target.value)}>
              <option value="all">all</option>
              <option value="passed">passed</option>
              <option value="warning">warning</option>
              <option value="failed">failed</option>
            </select>
            <input className="bg-dark-surface p-2 rounded text-sm" placeholder="fork id" value={runFilterFork} onChange={(e) => setRunFilterFork(e.target.value)} />
            <button className="border border-border-dark px-3 py-1 rounded text-sm" onClick={() => { setRunFilterScenario("all"); setRunFilterStatus("all"); setRunFilterFork(""); }}>Clear Filters</button>
          </div>
          <p className="mt-2 text-xs text-warm-silver">showing {runInspectionRows.length} of {runInspection.run.results.length} rows</p>
          <div className="mt-2 space-y-1 text-sm max-h-56 overflow-auto">
            {runInspectionRows.map((result) => (
              <div key={`${result.name}-${result.fork_id}`} className="border-b border-border-dark/50 pb-1">
                <span>{result.name}</span>
                <span className="text-warm-silver"> fork {result.fork_id}</span>
                {result.fork_parent_id ? <span className="text-warm-silver"> parent {result.fork_parent_id}</span> : null}
                <span className="text-warm-silver"> | {result.status}</span>
                <span className="text-warm-silver"> | score {result.score.toFixed(2)}</span>
                <span className="text-warm-silver"> | delay {result.network_delay_ms}ms</span>
                {result.warnings.length ? <span className="text-coral"> | {result.warnings[0]}</span> : null}
              </div>
            ))}
          </div>
          <div className="mt-4 border border-border-dark rounded p-3">
            <h3 className="text-sm mb-2">Trace Drilldown</h3>
            <div className="grid gap-2 md:grid-cols-3">
              <select className="bg-dark-surface p-2 rounded text-xs" value={traceFilterScenario} onChange={(e) => setTraceFilterScenario(e.target.value)}>
                {traceScenarioOptions.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
              <input
                className="bg-dark-surface p-2 rounded text-xs"
                placeholder="fork id"
                value={traceFilterFork}
                onChange={(e) => setTraceFilterFork(e.target.value)}
              />
              <button
                className="border border-border-dark px-3 py-1 rounded text-xs"
                onClick={() => {
                  setTraceFilterScenario("all");
                  setTraceFilterFork("");
                  setSelectedTraceKey("");
                }}
              >
                Clear Trace Filters
              </button>
            </div>
            <p className="mt-2 text-xs text-warm-silver">showing {filteredTraceRows.length} of {traceRows.length} traces</p>
            <div className="mt-2 grid gap-2 md:grid-cols-2">
              <div className="max-h-48 overflow-auto border border-border-dark rounded p-2 space-y-1">
                {filteredTraceRows.map((row) => (
                  <button
                    key={row.key}
                    className={`w-full text-left text-xs rounded p-2 border ${selectedTrace?.key === row.key ? "border-terracotta" : "border-border-dark"}`}
                    onClick={() => setSelectedTraceKey(row.key)}
                  >
                    {row.scenarioName} | fork {row.forkId || "n/a"}
                  </button>
                ))}
                {filteredTraceRows.length === 0 && <p className="text-xs text-warm-silver">No traces match filters.</p>}
              </div>
              <pre className="max-h-48 overflow-auto bg-dark-surface rounded p-2 text-[11px] leading-5 whitespace-pre-wrap">
                {selectedTrace ? JSON.stringify(selectedTrace.trace, null, 2) : "Select a trace to inspect payload"}
              </pre>
            </div>
          </div>
        </section>
      )}

      {compare && (
        <section className="border border-border-dark rounded-xl p-4 mt-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-xl">Multi-Baseline Compare</h2>
            <div className="flex gap-2">
              <button className="border border-border-dark px-3 py-1 rounded text-sm disabled:opacity-50" disabled={isSavingArtifact || !canEditSelectedCollection} onClick={() => void saveCompareArtifact()}>
                {isSavingArtifact ? "Saving..." : "Save Artifact"}
              </button>
              <button className="border border-border-dark px-3 py-1 rounded text-sm" onClick={exportCompareJson}>Export JSON</button>
              <button className="border border-border-dark px-3 py-1 rounded text-sm" onClick={exportCompareCsv}>Export CSV</button>
            </div>
          </div>
          {compare.diffs.map((d) => (
            <div key={d.baseline_id || d.baseline_run_id} className="mb-4 border border-border-dark rounded p-3">
              <p className="text-sm text-warm-silver">{d.baseline_label || "baseline"} ({d.baseline_run_id}) {"->"} {d.candidate_run_id} | score {d.score_delta >= 0 ? "+" : ""}{d.score_delta.toFixed(2)}</p>
              {d.trace_delta && (
                <p className="text-xs text-warm-silver mt-1">
                  traces {d.trace_delta.baseline_trace_count} {"->"} {d.trace_delta.candidate_trace_count}
                  {" "}({d.trace_delta.trace_count_delta >= 0 ? "+" : ""}{d.trace_delta.trace_count_delta})
                  {" "}warn delta {d.trace_delta.warning_event_delta >= 0 ? "+" : ""}{d.trace_delta.warning_event_delta}
                  {" "}backend {d.trace_delta.baseline_runtime_backend} {"->"} {d.trace_delta.candidate_runtime_backend}
                </p>
              )}
              {d.trace_delta && (d.trace_delta.chaos_targets_added.length > 0 || d.trace_delta.chaos_targets_removed.length > 0) && (
                <p className="text-xs text-warm-silver mt-1">
                  chaos +[{d.trace_delta.chaos_targets_added.join(", ") || "-"}] -[{d.trace_delta.chaos_targets_removed.join(", ") || "-"}]
                </p>
              )}
              <div className="mt-2 space-y-1 text-sm">
                {d.scenario_diffs.map((s) => (
                  <div key={`${d.baseline_run_id}-${s.name}`} className="flex justify-between border-b border-border-dark/50 pb-1">
                    <span>{s.name}</span>
                    <span>{s.baseline_status} {"->"} {s.candidate_status} | {s.baseline_score.toFixed(2)} {"->"} {s.candidate_score.toFixed(2)} | warn {s.warning_delta >= 0 ? "+" : ""}{s.warning_delta}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      <section className="border border-border-dark rounded-xl p-4 mt-4">
        <div className="flex items-center justify-between gap-2 mb-2">
          <h2 className="text-xl">Saved Compare Artifacts</h2>
          <div className="flex gap-2 items-center">
            <input
              className="bg-dark-surface p-2 rounded text-sm w-24"
              value={pruneKeepLatest}
              onChange={(e) => setPruneKeepLatest(e.target.value)}
              placeholder="keep"
            />
            <button className="border border-border-dark px-3 py-1 rounded text-sm disabled:opacity-50" disabled={!canEditSelectedCollection} onClick={() => void pruneSavedArtifacts()}>
              Prune
            </button>
          </div>
        </div>
        <div className="space-y-2 text-sm max-h-56 overflow-auto">
          {compareArtifacts.map((artifact) => (
            <div key={artifact.artifact_id} className="flex items-center justify-between border border-border-dark rounded p-2">
              <div>
                <div>{artifact.filename}</div>
                <div className="text-warm-silver">
                  {artifact.candidate_run_id} | baselines {artifact.baseline_ids.length} | {new Date(artifact.created_at).toLocaleString()}
                </div>
              </div>
              <div className="flex gap-2">
                <button className="border border-border-dark px-2 py-1 rounded disabled:opacity-50" disabled={!canViewSelectedCollection} onClick={() => void replayFromArtifact(artifact.artifact_id)}>Replay</button>
                <button className="border border-border-dark px-2 py-1 rounded disabled:opacity-50" disabled={!canViewSelectedCollection} onClick={() => void downloadSavedArtifact(artifact.artifact_id, "json")}>JSON</button>
                <button className="border border-border-dark px-2 py-1 rounded disabled:opacity-50" disabled={!canViewSelectedCollection} onClick={() => void downloadSavedArtifact(artifact.artifact_id, "csv")}>CSV</button>
                <button className="border border-coral px-2 py-1 rounded text-coral disabled:opacity-50" disabled={!canEditSelectedCollection} onClick={() => void deleteSavedArtifact(artifact.artifact_id)}>Delete</button>
              </div>
            </div>
          ))}
          {compareArtifacts.length === 0 && <p className="text-warm-silver">No saved compare artifacts yet.</p>}
        </div>
      </section>

      <section className="border border-border-dark rounded-xl p-4 mt-4">
        <h2 className="text-xl mb-2">Audit Events</h2>
        <div className="space-y-1 text-sm max-h-56 overflow-auto">
          {(overview?.audit_events || []).slice(0, 50).map((evt) => (
            <div key={evt.event_id} className="border-b border-border-dark/50 pb-1">
              <span className="text-warm-silver">{new Date(evt.created_at).toLocaleString()} </span>
              <span>{evt.actor_id}</span>
              <span className="text-warm-silver"> {evt.action} </span>
              <span>{evt.entity_type}:{evt.entity_id}</span>
            </div>
          ))}
          {(overview?.audit_events || []).length === 0 && <p className="text-warm-silver">No audit events yet.</p>}
        </div>
      </section>
    </main>
  );
}

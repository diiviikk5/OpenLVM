"use client";

import { useEffect, useMemo, useState } from "react";

type Workspace = { workspace_id: string; name: string };
type Collection = { collection_id: string; workspace_id: string; name: string };
type Baseline = { baseline_id: string; run_id: string; label: string };
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

  const [selectedCollection, setSelectedCollection] = useState("");
  const [selectedRun, setSelectedRun] = useState("");
  const [selectedBaselines, setSelectedBaselines] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [lastRunId, setLastRunId] = useState("");
  const [compare, setCompare] = useState<CompareResponse | null>(null);
  const [runInspection, setRunInspection] = useState<RunInspection | null>(null);
  const [runFilterScenario, setRunFilterScenario] = useState("all");
  const [runFilterStatus, setRunFilterStatus] = useState("all");
  const [runFilterFork, setRunFilterFork] = useState("");

  const [workspaceName, setWorkspaceName] = useState("");
  const [collectionWorkspace, setCollectionWorkspace] = useState("");
  const [collectionName, setCollectionName] = useState("");

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
        const data = await fetchOverview();
        setOverview(data);
        if (data.workspaces[0]) setCollectionWorkspace(data.workspaces[0].workspace_id);
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
  const scenarios = useMemo(
    () => (overview && selectedCollection ? overview.scenarios_by_collection[selectedCollection] || [] : []),
    [overview, selectedCollection]
  );

  const workspaceNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const ws of overview?.workspaces || []) map[ws.workspace_id] = ws.name;
    return map;
  }, [overview]);

  const toggleBaseline = (id: string) =>
    setSelectedBaselines((arr) => (arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id]));

  const setEditing = (s: Scenario) => {
    setScenarioEditId(s.scenario_id);
    setScenarioCollection(s.collection_id);
    setScenarioName(s.name);
    setScenarioConfig(s.config_path);
    setScenarioInput(s.input_text);
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
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    downloadText(`openlvm-compare-${stamp}.json`, JSON.stringify(compare, null, 2), "application/json");
  };

  const exportCompareCsv = () => {
    if (!compare) return;
    const header = [
      "baseline_id",
      "baseline_label",
      "baseline_run_id",
      "candidate_run_id",
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
    for (const diff of compare.diffs) {
      for (const scenario of diff.scenario_diffs) {
        lines.push(
          [
            diff.baseline_id || "",
            diff.baseline_label || "",
            diff.baseline_run_id,
            diff.candidate_run_id,
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
    downloadText(`openlvm-compare-${stamp}.csv`, lines.join("\n"), "text/csv");
  };

  return (
    <main className="min-h-screen bg-near-black text-ivory p-6">
      <h1 className="text-3xl mb-3">OpenLVM Workbench</h1>
      {error && <p className="text-coral mb-3">{error}</p>}
      {msg && <p className="text-accent-emerald mb-3">{msg}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        <section className="border border-border-dark rounded-xl p-4">
          <h2 className="text-xl mb-2">Setup</h2>
          <div className="space-y-2">
            <input className="w-full bg-dark-surface p-2 rounded" placeholder="Workspace name" value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)} />
            <button className="bg-terracotta px-3 py-1 rounded" onClick={async () => { try { await postJson("/api/workbench/workspace", { name: workspaceName }); setWorkspaceName(""); await load(); setMsg("Workspace created"); } catch (e) { setError(String(e)); } }}>Create Workspace</button>
            <button className="border border-border-dark px-3 py-1 rounded" onClick={async () => { try { if (!collectionWorkspace || !workspaceName) return; await postJson("/api/workbench/workspace", { workspace_id: collectionWorkspace, name: workspaceName }, "PATCH"); setWorkspaceName(""); await load(); setMsg("Workspace updated"); } catch (e) { setError(String(e)); } }}>Update Selected Workspace</button>
            <button className="border border-coral px-3 py-1 rounded text-coral" onClick={async () => { try { if (!collectionWorkspace) return; await postJson("/api/workbench/workspace", { workspace_id: collectionWorkspace }, "DELETE"); await load(); setMsg("Workspace deleted"); } catch (e) { setError(String(e)); } }}>Delete Selected Workspace</button>
            <select className="w-full bg-dark-surface p-2 rounded" value={collectionWorkspace} onChange={(e) => setCollectionWorkspace(e.target.value)}>
              {(overview?.workspaces || []).map((w) => <option key={w.workspace_id} value={w.workspace_id}>{w.name}</option>)}
            </select>
            <input className="w-full bg-dark-surface p-2 rounded" placeholder="Collection name" value={collectionName} onChange={(e) => setCollectionName(e.target.value)} />
            <button className="bg-terracotta px-3 py-1 rounded" onClick={async () => { try { const c = await postJson<Collection>("/api/workbench/collection", { workspace_id: collectionWorkspace, name: collectionName }); setCollectionName(""); setSelectedCollection(c.collection_id); setScenarioCollection(c.collection_id); await load(); setMsg("Collection created"); } catch (e) { setError(String(e)); } }}>Create Collection</button>
            <button className="border border-border-dark px-3 py-1 rounded" onClick={async () => { try { if (!selectedCollection || !collectionName) return; await postJson("/api/workbench/collection", { collection_id: selectedCollection, name: collectionName }, "PATCH"); setCollectionName(""); await load(); setMsg("Collection updated"); } catch (e) { setError(String(e)); } }}>Update Selected Collection</button>
            <button className="border border-coral px-3 py-1 rounded text-coral" onClick={async () => { try { if (!selectedCollection) return; await postJson("/api/workbench/collection", { collection_id: selectedCollection }, "DELETE"); await load(); setMsg("Collection deleted"); } catch (e) { setError(String(e)); } }}>Delete Selected Collection</button>
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
              <button className="bg-terracotta px-3 py-1 rounded" onClick={async () => { try { if (scenarioEditId) { await postJson("/api/workbench/scenario", { scenario_id: scenarioEditId, name: scenarioName, config_path: scenarioConfig, input_text: scenarioInput }, "PATCH"); } else { await postJson("/api/workbench/scenario", { collection_id: scenarioCollection, name: scenarioName, config_path: scenarioConfig, input_text: scenarioInput }); } setScenarioEditId(""); setScenarioName(""); setScenarioInput(""); setScenarioConfig("examples/swarm.yaml"); await load(); setMsg("Scenario saved"); } catch (e) { setError(String(e)); } }}>{scenarioEditId ? "Update" : "Save"}</button>
              {scenarioEditId && <button className="border border-border-dark px-3 py-1 rounded" onClick={() => { setScenarioEditId(""); setScenarioName(""); setScenarioInput(""); setScenarioConfig("examples/swarm.yaml"); }}>Cancel</button>}
            </div>
          </div>
        </section>
      </div>

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
                <button className="border border-coral px-2 py-1 rounded text-coral" onClick={async () => { try { await postJson("/api/workbench/scenario", { scenario_id: s.scenario_id }, "DELETE"); await load(); setMsg("Scenario deleted"); } catch (e) { setError(String(e)); } }}>Delete</button>
              </div>
            </div>
          ))}
          {scenarios.length === 0 && <p className="text-warm-silver">No scenarios yet.</p>}
        </div>
      </section>

      <section className="border border-border-dark rounded-xl p-4 mt-4">
        <h2 className="text-xl mb-2">Run and Compare</h2>
        <div className="grid gap-2 md:grid-cols-3">
          <select className="bg-dark-surface p-2 rounded" value={selectedCollection} onChange={(e) => setSelectedCollection(e.target.value)}>
            {(overview?.collections || []).map((c) => <option key={c.collection_id} value={c.collection_id}>{c.name}</option>)}
          </select>
          <select className="bg-dark-surface p-2 rounded" value={selectedRun} onChange={(e) => setSelectedRun(e.target.value)}>
            {(overview?.recent_runs || []).map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id}</option>)}
          </select>
          <button className="bg-terracotta px-3 py-1 rounded" disabled={isRunning} onClick={async () => { try { setIsRunning(true); const run = await postJson<Run>("/api/workbench/run", { collection_id: selectedCollection }); setLastRunId(run.run_id); setSelectedRun(run.run_id); setBaselineRun(run.run_id); await load(); setMsg(`Run complete: ${run.run_id}`); } catch (e) { setError(String(e)); } finally { setIsRunning(false); } }}>{isRunning ? "Running..." : "Run Collection"}</button>
        </div>
        <div className="mt-2 p-2 border border-border-dark rounded">
          <p className="text-sm text-warm-silver mb-1">Choose baseline(s)</p>
          {baselines.map((b) => (
            <label key={b.baseline_id} className="block text-sm">
              <input type="checkbox" checked={selectedBaselines.includes(b.baseline_id)} onChange={() => toggleBaseline(b.baseline_id)} /> {b.label} ({b.run_id})
            </label>
          ))}
          {baselines.length === 0 && <p className="text-sm text-warm-silver">No baselines.</p>}
        </div>
        <div className="mt-2 flex gap-2">
          <input className="bg-dark-surface p-2 rounded flex-1" placeholder="Baseline run id" value={baselineRun} onChange={(e) => setBaselineRun(e.target.value)} />
          <input className="bg-dark-surface p-2 rounded w-40" placeholder="Label" value={baselineLabel} onChange={(e) => setBaselineLabel(e.target.value)} />
          <button className="border border-border-dark px-3 py-1 rounded" onClick={async () => { try { await postJson("/api/workbench/baseline", { collection_id: selectedCollection, run_id: baselineRun, label: baselineLabel }); await load(); setMsg("Baseline saved"); } catch (e) { setError(String(e)); } }}>Save Baseline</button>
          <button className="bg-terracotta px-3 py-1 rounded" disabled={isComparing} onClick={async () => { try { setIsComparing(true); const resp = await postJson<CompareResponse>("/api/workbench/compare", { collection_id: selectedCollection, run_id: selectedRun, baseline_ids: selectedBaselines }); setCompare(resp); setMsg(`Compared ${resp.diffs.length} baseline(s)`); } catch (e) { setError(String(e)); } finally { setIsComparing(false); } }}>{isComparing ? "Comparing..." : "Compare"}</button>
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
        </section>
      )}

      {compare && (
        <section className="border border-border-dark rounded-xl p-4 mt-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-xl">Multi-Baseline Compare</h2>
            <div className="flex gap-2">
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

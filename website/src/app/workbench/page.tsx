"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Workspace = {
  workspace_id: string;
  name: string;
  description: string;
  created_at: string;
};

type Collection = {
  collection_id: string;
  workspace_id: string;
  name: string;
  description: string;
  created_at: string;
};

type Baseline = {
  baseline_id: string;
  collection_id: string;
  run_id: string;
  label: string;
  created_at: string;
};

type ScenarioDiff = {
  name: string;
  baseline_status: string;
  candidate_status: string;
  baseline_score: number;
  candidate_score: number;
  score_delta: number;
  baseline_delay_ms: number;
  candidate_delay_ms: number;
  warning_delta: number;
};

type RunDiff = {
  baseline_run_id: string;
  candidate_run_id: string;
  summary_delta: Record<string, number>;
  score_delta: number;
  baseline_average_score: number;
  candidate_average_score: number;
  scenario_diffs: ScenarioDiff[];
  trace_delta: Record<string, string | number | boolean | string[]>;
};

type EvalRun = {
  run_id: string;
  suite_name: string;
  suite_version: string;
  started_at: string;
  scenarios_executed: number;
  summary: Record<string, number>;
  metadata: Record<string, unknown>;
};

type OverviewResponse = {
  workspaces: Workspace[];
  collections: Collection[];
  baselines_by_collection: Record<string, Baseline[]>;
  recent_runs: EvalRun[];
};

async function loadOverview(): Promise<OverviewResponse> {
  const res = await fetch("/api/workbench/overview", { cache: "no-store" });
  const data = (await res.json()) as OverviewResponse | { error: string };
  if (!res.ok || "error" in data) {
    throw new Error("error" in data ? data.error : "Failed to load workbench overview");
  }
  return data;
}

function formatTimestamp(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function WorkbenchPage() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);

  const [selectedCollectionId, setSelectedCollectionId] = useState<string>("");
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [lastRunId, setLastRunId] = useState<string>("");
  const [compareResult, setCompareResult] = useState<RunDiff | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDescription, setWorkspaceDescription] = useState("");
  const [collectionWorkspaceId, setCollectionWorkspaceId] = useState("");
  const [collectionName, setCollectionName] = useState("");
  const [collectionDescription, setCollectionDescription] = useState("");
  const [scenarioCollectionId, setScenarioCollectionId] = useState("");
  const [scenarioName, setScenarioName] = useState("");
  const [scenarioConfigPath, setScenarioConfigPath] = useState("examples/swarm.yaml");
  const [scenarioInputText, setScenarioInputText] = useState("");
  const [baselineCollectionId, setBaselineCollectionId] = useState("");
  const [baselineRunId, setBaselineRunId] = useState("");
  const [baselineLabel, setBaselineLabel] = useState("stable");

  useEffect(() => {
    void (async () => {
      try {
        const data = await loadOverview();
        setOverview(data);

        if (data.workspaces.length > 0) {
          setCollectionWorkspaceId(data.workspaces[0].workspace_id);
        }
        if (data.collections.length > 0) {
          const firstCollection = data.collections[0].collection_id;
          setSelectedCollectionId(firstCollection);
          setScenarioCollectionId(firstCollection);
          setBaselineCollectionId(firstCollection);
        }
        if (data.recent_runs.length > 0) {
          const latestRun = data.recent_runs[0].run_id;
          setSelectedRunId(latestRun);
          setBaselineRunId(latestRun);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load overview");
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const workspaceNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const workspace of overview?.workspaces ?? []) {
      map[workspace.workspace_id] = workspace.name;
    }
    return map;
  }, [overview]);

  const selectedCollectionBaselines = useMemo(() => {
    if (!overview || !selectedCollectionId) {
      return [];
    }
    return overview.baselines_by_collection[selectedCollectionId] ?? [];
  }, [overview, selectedCollectionId]);

  const refreshOverview = async () => {
    const data = await loadOverview();
    setOverview(data);

    if (data.workspaces.length > 0 && !collectionWorkspaceId) {
      setCollectionWorkspaceId(data.workspaces[0].workspace_id);
    }
    if (data.collections.length > 0 && !selectedCollectionId) {
      const collectionId = data.collections[0].collection_id;
      setSelectedCollectionId(collectionId);
      setScenarioCollectionId(collectionId);
      setBaselineCollectionId(collectionId);
    }
    if (data.recent_runs.length > 0 && !selectedRunId) {
      const runId = data.recent_runs[0].run_id;
      setSelectedRunId(runId);
      setBaselineRunId(runId);
    }
  };

  const postJson = async <T,>(url: string, payload: Record<string, unknown>): Promise<T> => {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = (await res.json()) as T | { error: string };
    if (!res.ok || (typeof data === "object" && data !== null && "error" in data)) {
      throw new Error((data as { error: string }).error || "Request failed");
    }
    return data as T;
  };

  const runCollection = async () => {
    if (!selectedCollectionId) return;
    setIsRunning(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const data = await postJson<EvalRun>("/api/workbench/run", {
        collection_id: selectedCollectionId,
      });
      setLastRunId(data.run_id);
      setSelectedRunId(data.run_id);
      setBaselineRunId(data.run_id);
      await refreshOverview();
      setActionSuccess(`Collection run complete: ${data.run_id}`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Collection run failed");
    } finally {
      setIsRunning(false);
    }
  };

  const compareBaseline = async () => {
    if (!selectedCollectionId || !selectedRunId) return;
    setIsComparing(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const data = await postJson<RunDiff>("/api/workbench/compare", {
        collection_id: selectedCollectionId,
        run_id: selectedRunId,
      });
      setCompareResult(data);
      setActionSuccess("Baseline comparison complete.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Baseline compare failed");
    } finally {
      setIsComparing(false);
    }
  };

  const createWorkspace = async () => {
    if (!workspaceName.trim()) return;
    setIsMutating(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const created = await postJson<Workspace>("/api/workbench/workspace", {
        name: workspaceName.trim(),
        description: workspaceDescription.trim(),
      });
      setWorkspaceName("");
      setWorkspaceDescription("");
      setCollectionWorkspaceId(created.workspace_id);
      await refreshOverview();
      setActionSuccess(`Workspace created: ${created.name}`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Workspace creation failed");
    } finally {
      setIsMutating(false);
    }
  };

  const createCollection = async () => {
    if (!collectionWorkspaceId || !collectionName.trim()) return;
    setIsMutating(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const created = await postJson<Collection>("/api/workbench/collection", {
        workspace_id: collectionWorkspaceId,
        name: collectionName.trim(),
        description: collectionDescription.trim(),
      });
      setCollectionName("");
      setCollectionDescription("");
      setSelectedCollectionId(created.collection_id);
      setScenarioCollectionId(created.collection_id);
      setBaselineCollectionId(created.collection_id);
      await refreshOverview();
      setActionSuccess(`Collection created: ${created.name}`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Collection creation failed");
    } finally {
      setIsMutating(false);
    }
  };

  const saveScenario = async () => {
    if (!scenarioCollectionId || !scenarioName.trim() || !scenarioConfigPath.trim() || !scenarioInputText.trim()) return;
    setIsMutating(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await postJson("/api/workbench/scenario", {
        collection_id: scenarioCollectionId,
        name: scenarioName.trim(),
        config_path: scenarioConfigPath.trim(),
        input_text: scenarioInputText.trim(),
      });
      setScenarioName("");
      setScenarioInputText("");
      await refreshOverview();
      setActionSuccess("Scenario saved.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Scenario save failed");
    } finally {
      setIsMutating(false);
    }
  };

  const saveBaseline = async () => {
    if (!baselineCollectionId || !baselineRunId.trim() || !baselineLabel.trim()) return;
    setIsMutating(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await postJson("/api/workbench/baseline", {
        collection_id: baselineCollectionId,
        run_id: baselineRunId.trim(),
        label: baselineLabel.trim(),
      });
      await refreshOverview();
      setActionSuccess(`Baseline saved: ${baselineLabel.trim()}`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Baseline save failed");
    } finally {
      setIsMutating(false);
    }
  };

  if (isLoading) {
    return (
      <main className="min-h-screen bg-near-black p-10 text-ivory">
        <p className="text-lg text-warm-silver">Loading OpenLVM workbench...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-near-black p-10 text-ivory">
        <h1 className="text-3xl font-semibold">Workbench unavailable</h1>
        <p className="mt-4 text-coral">{error}</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(201,100,66,0.18),transparent_34%),linear-gradient(180deg,#141413_0%,#1b1a19_100%)] text-ivory">
      <div className="mx-auto max-w-[1280px] px-6 py-10 lg:px-10 lg:py-14">
        <div className="glass-dark-elevated mb-8 rounded-[28px] border border-border-dark p-6 lg:p-8">
          <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="mb-3 text-sm uppercase tracking-[0.28em] text-warm-silver">OpenLVM Workbench</p>
              <h1 className="font-[family-name:var(--font-serif)] text-4xl leading-tight text-ivory lg:text-6xl">
                Live collection runs, baselines, and trace-aware diffs.
              </h1>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                href="https://github.com/diiviikk5/OpenLVM"
                target="_blank"
                className="rounded-2xl border border-border-dark px-4 py-3 text-sm font-medium text-warm-silver transition hover:border-olive-gray hover:text-ivory"
              >
                View Repository
              </Link>
              <button
                type="button"
                onClick={() => void refreshOverview()}
                className="rounded-2xl bg-terracotta px-4 py-3 text-sm font-medium text-ivory transition hover:bg-coral"
              >
                Refresh
              </button>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-2xl border border-border-dark bg-near-black/60 p-4">
              <p className="text-sm text-stone-gray">Workspaces</p>
              <p className="mt-2 text-3xl font-semibold text-ivory">{overview?.workspaces.length ?? 0}</p>
            </div>
            <div className="rounded-2xl border border-border-dark bg-near-black/60 p-4">
              <p className="text-sm text-stone-gray">Collections</p>
              <p className="mt-2 text-3xl font-semibold text-ivory">{overview?.collections.length ?? 0}</p>
            </div>
            <div className="rounded-2xl border border-border-dark bg-near-black/60 p-4">
              <p className="text-sm text-stone-gray">Recent Runs</p>
              <p className="mt-2 text-3xl font-semibold text-ivory">{overview?.recent_runs.length ?? 0}</p>
            </div>
          </div>
        </div>

        <section className="glass-dark mb-6 rounded-[28px] border border-border-dark p-6">
          <h2 className="text-2xl font-semibold">Setup</h2>
          <p className="mt-2 text-sm text-warm-silver">
            Create workspaces, collections, scenarios, and baselines without leaving the workbench.
          </p>
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <div className="rounded-2xl border border-border-dark bg-near-black/45 p-4">
              <h3 className="text-lg font-semibold">Create Workspace</h3>
              <input
                className="mt-3 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                placeholder="Workspace name"
                value={workspaceName}
                onChange={(event) => setWorkspaceName(event.target.value)}
              />
              <input
                className="mt-2 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                placeholder="Description (optional)"
                value={workspaceDescription}
                onChange={(event) => setWorkspaceDescription(event.target.value)}
              />
              <button
                type="button"
                onClick={() => void createWorkspace()}
                disabled={isMutating}
                className="mt-3 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-ivory transition hover:bg-coral disabled:opacity-50"
              >
                Create Workspace
              </button>
            </div>

            <div className="rounded-2xl border border-border-dark bg-near-black/45 p-4">
              <h3 className="text-lg font-semibold">Create Collection</h3>
              <select
                className="mt-3 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                value={collectionWorkspaceId}
                onChange={(event) => setCollectionWorkspaceId(event.target.value)}
              >
                {(overview?.workspaces ?? []).map((workspace) => (
                  <option key={workspace.workspace_id} value={workspace.workspace_id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
              <input
                className="mt-2 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                placeholder="Collection name"
                value={collectionName}
                onChange={(event) => setCollectionName(event.target.value)}
              />
              <input
                className="mt-2 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                placeholder="Description (optional)"
                value={collectionDescription}
                onChange={(event) => setCollectionDescription(event.target.value)}
              />
              <button
                type="button"
                onClick={() => void createCollection()}
                disabled={isMutating || (overview?.workspaces.length ?? 0) === 0}
                className="mt-3 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-ivory transition hover:bg-coral disabled:opacity-50"
              >
                Create Collection
              </button>
            </div>

            <div className="rounded-2xl border border-border-dark bg-near-black/45 p-4">
              <h3 className="text-lg font-semibold">Save Scenario</h3>
              <select
                className="mt-3 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                value={scenarioCollectionId}
                onChange={(event) => setScenarioCollectionId(event.target.value)}
              >
                {(overview?.collections ?? []).map((collection) => (
                  <option key={collection.collection_id} value={collection.collection_id}>
                    {collection.name}
                  </option>
                ))}
              </select>
              <input
                className="mt-2 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                placeholder="Scenario name"
                value={scenarioName}
                onChange={(event) => setScenarioName(event.target.value)}
              />
              <input
                className="mt-2 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                placeholder="Config path (e.g. examples/swarm.yaml)"
                value={scenarioConfigPath}
                onChange={(event) => setScenarioConfigPath(event.target.value)}
              />
              <textarea
                className="mt-2 h-24 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                placeholder="Scenario input"
                value={scenarioInputText}
                onChange={(event) => setScenarioInputText(event.target.value)}
              />
              <button
                type="button"
                onClick={() => void saveScenario()}
                disabled={isMutating || (overview?.collections.length ?? 0) === 0}
                className="mt-3 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-ivory transition hover:bg-coral disabled:opacity-50"
              >
                Save Scenario
              </button>
            </div>

            <div className="rounded-2xl border border-border-dark bg-near-black/45 p-4">
              <h3 className="text-lg font-semibold">Save Baseline</h3>
              <select
                className="mt-3 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                value={baselineCollectionId}
                onChange={(event) => setBaselineCollectionId(event.target.value)}
              >
                {(overview?.collections ?? []).map((collection) => (
                  <option key={collection.collection_id} value={collection.collection_id}>
                    {collection.name}
                  </option>
                ))}
              </select>
              <input
                className="mt-2 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                placeholder="Run ID"
                value={baselineRunId}
                onChange={(event) => setBaselineRunId(event.target.value)}
              />
              <input
                className="mt-2 w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                placeholder="Label"
                value={baselineLabel}
                onChange={(event) => setBaselineLabel(event.target.value)}
              />
              <button
                type="button"
                onClick={() => void saveBaseline()}
                disabled={isMutating || (overview?.collections.length ?? 0) === 0}
                className="mt-3 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-ivory transition hover:bg-coral disabled:opacity-50"
              >
                Save Baseline
              </button>
            </div>
          </div>
          {actionSuccess && <p className="mt-3 text-sm text-accent-emerald">{actionSuccess}</p>}
          {actionError && <p className="mt-2 text-sm text-coral">{actionError}</p>}
        </section>

        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <section className="glass-dark rounded-[28px] border border-border-dark p-6">
            <h2 className="text-2xl font-semibold">Collections</h2>
            <p className="mt-2 text-sm text-warm-silver">Select a collection and execute from the workbench.</p>
            <div className="mt-4 space-y-3">
              {(overview?.collections ?? []).map((collection) => (
                <button
                  key={collection.collection_id}
                  type="button"
                  onClick={() => setSelectedCollectionId(collection.collection_id)}
                  className={`w-full rounded-2xl border p-4 text-left transition ${
                    selectedCollectionId === collection.collection_id
                      ? "border-terracotta bg-terracotta/10"
                      : "border-border-dark bg-near-black/50 hover:border-olive-gray"
                  }`}
                >
                  <p className="text-lg font-semibold text-ivory">{collection.name}</p>
                  <p className="text-sm text-warm-silver">
                    {workspaceNameById[collection.workspace_id] ?? collection.workspace_id}
                  </p>
                </button>
              ))}
            </div>
          </section>

          <section className="glass-dark rounded-[28px] border border-border-dark p-6">
            <h2 className="text-2xl font-semibold">Run + Compare</h2>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm text-stone-gray">Collection</label>
                <select
                  className="w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                  value={selectedCollectionId}
                  onChange={(event) => setSelectedCollectionId(event.target.value)}
                >
                  {(overview?.collections ?? []).map((collection) => (
                    <option key={collection.collection_id} value={collection.collection_id}>
                      {collection.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm text-stone-gray">Run ID for compare</label>
                <select
                  className="w-full rounded-xl border border-border-dark bg-near-black px-3 py-2 text-ivory"
                  value={selectedRunId}
                  onChange={(event) => setSelectedRunId(event.target.value)}
                >
                  {(overview?.recent_runs ?? []).map((run) => (
                    <option key={run.run_id} value={run.run_id}>
                      {run.run_id}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void runCollection()}
                disabled={isRunning || !selectedCollectionId}
                className="rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-ivory transition hover:bg-coral disabled:opacity-50"
              >
                {isRunning ? "Running..." : "Run Collection"}
              </button>
              <button
                type="button"
                onClick={() => void compareBaseline()}
                disabled={isComparing || !selectedCollectionId || !selectedRunId}
                className="rounded-xl border border-border-dark bg-near-black px-4 py-2 text-sm font-semibold text-ivory transition hover:border-olive-gray disabled:opacity-50"
              >
                {isComparing ? "Comparing..." : "Compare To Baseline"}
              </button>
            </div>

            {selectedCollectionBaselines.length > 0 && (
              <p className="mt-3 text-sm text-warm-silver">
                Baseline: {selectedCollectionBaselines[0].label} ({selectedCollectionBaselines[0].run_id})
              </p>
            )}
            {lastRunId && <p className="mt-2 text-sm text-accent-emerald">Latest run created: {lastRunId}</p>}
          </section>
        </div>

        <section className="glass-dark mt-6 rounded-[28px] border border-border-dark p-6">
          <h2 className="text-2xl font-semibold">Recent Runs</h2>
          <div className="mt-4 overflow-hidden rounded-2xl border border-border-dark">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-dark-surface/70 text-stone-gray">
                <tr>
                  <th className="px-4 py-3 font-medium">Run ID</th>
                  <th className="px-4 py-3 font-medium">Suite</th>
                  <th className="px-4 py-3 font-medium">Scenarios</th>
                  <th className="px-4 py-3 font-medium">Passed</th>
                  <th className="px-4 py-3 font-medium">Warnings</th>
                  <th className="px-4 py-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {(overview?.recent_runs ?? []).map((run) => (
                  <tr key={run.run_id} className="border-t border-border-dark bg-near-black/50 text-warm-silver">
                    <td className="px-4 py-3 font-[family-name:var(--font-jetbrains)] text-ivory">{run.run_id}</td>
                    <td className="px-4 py-3">{run.suite_name}</td>
                    <td className="px-4 py-3">{run.scenarios_executed}</td>
                    <td className="px-4 py-3">{run.summary.passed ?? 0}</td>
                    <td className="px-4 py-3">{run.summary.warnings ?? 0}</td>
                    <td className="px-4 py-3">{formatTimestamp(run.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {compareResult && (
          <section className="glass-dark mt-6 rounded-[28px] border border-border-dark p-6">
            <h2 className="text-2xl font-semibold">Baseline Diff</h2>
            <p className="mt-2 text-sm text-warm-silver">
              {compareResult.baseline_run_id} {"->"} {compareResult.candidate_run_id} | score delta{" "}
              {compareResult.score_delta >= 0 ? "+" : ""}
              {compareResult.score_delta.toFixed(2)}
            </p>
            <div className="mt-4 overflow-hidden rounded-2xl border border-border-dark">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="bg-dark-surface/70 text-stone-gray">
                  <tr>
                    <th className="px-4 py-3 font-medium">Scenario</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Score</th>
                    <th className="px-4 py-3 font-medium">Delay</th>
                    <th className="px-4 py-3 font-medium">Warn Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {compareResult.scenario_diffs.map((diff) => (
                    <tr key={diff.name} className="border-t border-border-dark bg-near-black/50 text-warm-silver">
                      <td className="px-4 py-3 text-ivory">{diff.name}</td>
                      <td className="px-4 py-3">
                        {diff.baseline_status} {"->"} {diff.candidate_status}
                      </td>
                      <td className="px-4 py-3">
                        {diff.baseline_score.toFixed(2)} {"->"} {diff.candidate_score.toFixed(2)}
                      </td>
                      <td className="px-4 py-3">
                        {diff.baseline_delay_ms}ms {"->"} {diff.candidate_delay_ms}ms
                      </td>
                      <td className="px-4 py-3">
                        {diff.warning_delta >= 0 ? "+" : ""}
                        {diff.warning_delta}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

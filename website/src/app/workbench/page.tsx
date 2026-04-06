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
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>("");
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [lastRunId, setLastRunId] = useState<string>("");
  const [compareResult, setCompareResult] = useState<RunDiff | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const data = await loadOverview();
        setOverview(data);
        if (data.collections.length > 0) {
          setSelectedCollectionId(data.collections[0].collection_id);
        }
        if (data.recent_runs.length > 0) {
          setSelectedRunId(data.recent_runs[0].run_id);
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
  };

  const runCollection = async () => {
    if (!selectedCollectionId) {
      return;
    }
    setIsRunning(true);
    setActionError(null);
    try {
      const res = await fetch("/api/workbench/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collection_id: selectedCollectionId }),
      });
      const data = (await res.json()) as EvalRun | { error: string };
      if (!res.ok || "error" in data) {
        throw new Error("error" in data ? data.error : "Collection run failed");
      }
      setLastRunId(data.run_id);
      setSelectedRunId(data.run_id);
      await refreshOverview();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Collection run failed");
    } finally {
      setIsRunning(false);
    }
  };

  const compareBaseline = async () => {
    if (!selectedCollectionId || !selectedRunId) {
      return;
    }
    setIsComparing(true);
    setActionError(null);
    try {
      const res = await fetch("/api/workbench/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          collection_id: selectedCollectionId,
          run_id: selectedRunId,
        }),
      });
      const data = (await res.json()) as RunDiff | { error: string };
      if (!res.ok || "error" in data) {
        throw new Error("error" in data ? data.error : "Baseline compare failed");
      }
      setCompareResult(data);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Baseline compare failed");
    } finally {
      setIsComparing(false);
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
            {actionError && <p className="mt-2 text-sm text-coral">{actionError}</p>}
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
                    <th className="px-4 py-3 font-medium">Warn Δ</th>
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
                      <td className="px-4 py-3">{diff.warning_delta >= 0 ? "+" : ""}{diff.warning_delta}</td>
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

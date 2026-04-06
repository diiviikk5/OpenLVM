import Link from "next/link";

const collections = [
  {
    name: "Support Regression",
    workspace: "Customer Ops",
    scenarios: 12,
    baselines: 3,
    status: "stable",
  },
  {
    name: "Tool Permission Audit",
    workspace: "Core Runtime",
    scenarios: 8,
    baselines: 2,
    status: "watch",
  },
  {
    name: "MCP Contract Drift",
    workspace: "Integrations",
    scenarios: 5,
    baselines: 4,
    status: "new",
  },
];

const recentRuns = [
  {
    id: "run-9ad31b2",
    collection: "Support Regression",
    backend: "zig",
    passed: 10,
    warnings: 2,
    diff: "-0.04",
  },
  {
    id: "run-91bc662",
    collection: "Tool Permission Audit",
    backend: "simulated",
    passed: 7,
    warnings: 1,
    diff: "+0.01",
  },
  {
    id: "run-6ab19ef",
    collection: "MCP Contract Drift",
    backend: "zig",
    passed: 5,
    warnings: 0,
    diff: "+0.00",
  },
];

const diffRows = [
  {
    scenario: "cancel-flow",
    status: "passed -> warning",
    score: "0.95 -> 0.72",
    trace: "1 -> 2",
  },
  {
    scenario: "refund-flow",
    status: "passed -> passed",
    score: "0.91 -> 0.89",
    trace: "1 -> 1",
  },
  {
    scenario: "escalation-flow",
    status: "warning -> passed",
    score: "0.74 -> 0.88",
    trace: "2 -> 1",
  },
];

const commands = [
  "openlvm workspace-create 'Customer Ops'",
  "openlvm collection-create ws-123 'Support Regression'",
  "openlvm scenario-save col-123 cancel-flow examples/swarm.yaml 'Cancel my plan'",
  "openlvm collection-run col-123 --chaos network_delay",
  "openlvm baseline-compare col-123 latest",
];

function statusClasses(status: string): string {
  if (status === "stable") {
    return "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/30";
  }
  if (status === "watch") {
    return "bg-accent-amber/15 text-accent-amber border-accent-amber/30";
  }
  return "bg-terracotta/15 text-terracotta border-terracotta/30";
}

export default function WorkbenchPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(201,100,66,0.18),transparent_34%),linear-gradient(180deg,#141413_0%,#1b1a19_100%)] text-ivory">
      <div className="mx-auto max-w-[1280px] px-6 py-10 lg:px-10 lg:py-14">
        <div className="glass-dark-elevated mb-8 rounded-[28px] border border-border-dark p-6 lg:p-8">
          <div className="mb-8 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="mb-3 text-sm uppercase tracking-[0.28em] text-warm-silver">
                OpenLVM Workbench
              </p>
              <h1 className="font-[family-name:var(--font-serif)] text-4xl leading-tight text-ivory lg:text-6xl">
                Postman-style control room for agent testing.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-warm-silver lg:text-lg">
                Save collections, rerun agent sessions, diff traces against baselines, and inspect
                what changed before a prompt or runtime update reaches production.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                href="https://github.com/diiviikk5/OpenLVM"
                target="_blank"
                className="rounded-2xl border border-border-dark px-4 py-3 text-sm font-medium text-warm-silver transition hover:border-olive-gray hover:text-ivory"
              >
                View Repository
              </Link>
              <Link
                href="/#quickstart"
                className="rounded-2xl bg-terracotta px-4 py-3 text-sm font-medium text-ivory transition hover:bg-coral"
              >
                Start With CLI
              </Link>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
            <section className="rounded-[24px] border border-border-dark bg-deep-dark/70 p-5 terminal-shadow">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-stone-gray">Command Flow</p>
                  <h2 className="mt-2 text-xl font-semibold text-ivory">Collections to baselines</h2>
                </div>
                <span className="rounded-full border border-terracotta/30 bg-terracotta/10 px-3 py-1 text-xs font-medium text-coral">
                  CLI + MCP
                </span>
              </div>
              <div className="space-y-3 font-[family-name:var(--font-jetbrains)] text-sm text-warm-silver">
                {commands.map((command) => (
                  <div
                    key={command}
                    className="rounded-2xl border border-border-dark bg-near-black/80 px-4 py-3"
                  >
                    <span className="mr-3 text-coral">$</span>
                    {command}
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-[24px] border border-border-dark bg-[linear-gradient(180deg,rgba(48,48,46,0.68),rgba(20,20,19,0.92))] p-5">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-gray">Why This Layer</p>
              <div className="mt-4 grid gap-4">
                <div className="rounded-2xl border border-border-dark bg-near-black/70 p-4">
                  <p className="text-sm text-stone-gray">Trace delta</p>
                  <p className="mt-2 text-3xl font-semibold text-ivory">+1 warning event</p>
                  <p className="mt-2 text-sm text-warm-silver">
                    Candidate run introduced an extra delayed tool path on the executor agent.
                  </p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-2xl border border-border-dark bg-near-black/70 p-4">
                    <p className="text-sm text-stone-gray">Runtime backends</p>
                    <p className="mt-2 text-lg font-semibold text-ivory">simulated -&gt; zig</p>
                  </div>
                  <div className="rounded-2xl border border-border-dark bg-near-black/70 p-4">
                    <p className="text-sm text-stone-gray">Chaos targets</p>
                    <p className="mt-2 text-lg font-semibold text-ivory">executor added</p>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <section className="glass-dark rounded-[28px] border border-border-dark p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-stone-gray">Collections</p>
                <h2 className="mt-2 text-2xl font-semibold text-ivory">Saved workspaces and suites</h2>
              </div>
              <span className="rounded-full border border-border-dark px-3 py-1 text-xs text-warm-silver">
                local-first
              </span>
            </div>
            <div className="space-y-4">
              {collections.map((collection) => (
                <div
                  key={collection.name}
                  className="rounded-[24px] border border-border-dark bg-dark-surface/35 p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold text-ivory">{collection.name}</h3>
                      <p className="mt-1 text-sm text-warm-silver">{collection.workspace}</p>
                    </div>
                    <span
                      className={`rounded-full border px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] ${statusClasses(collection.status)}`}
                    >
                      {collection.status}
                    </span>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-warm-silver">
                    <div className="rounded-2xl bg-near-black/60 px-4 py-3">
                      <p className="text-stone-gray">Scenarios</p>
                      <p className="mt-2 text-xl font-semibold text-ivory">{collection.scenarios}</p>
                    </div>
                    <div className="rounded-2xl bg-near-black/60 px-4 py-3">
                      <p className="text-stone-gray">Baselines</p>
                      <p className="mt-2 text-xl font-semibold text-ivory">{collection.baselines}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-6">
            <div className="glass-dark rounded-[28px] border border-border-dark p-6">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-stone-gray">Recent Runs</p>
                  <h2 className="mt-2 text-2xl font-semibold text-ivory">Inspect the latest branch of behavior</h2>
                </div>
                <span className="rounded-full bg-terracotta/10 px-3 py-1 text-xs font-medium text-coral">
                  replay-ready
                </span>
              </div>
              <div className="overflow-hidden rounded-[24px] border border-border-dark">
                <table className="w-full border-collapse text-left text-sm">
                  <thead className="bg-dark-surface/70 text-stone-gray">
                    <tr>
                      <th className="px-4 py-3 font-medium">Run</th>
                      <th className="px-4 py-3 font-medium">Collection</th>
                      <th className="px-4 py-3 font-medium">Backend</th>
                      <th className="px-4 py-3 font-medium">Pass/Warn</th>
                      <th className="px-4 py-3 font-medium">Score Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentRuns.map((run) => (
                      <tr key={run.id} className="border-t border-border-dark bg-near-black/55 text-warm-silver">
                        <td className="px-4 py-3 font-[family-name:var(--font-jetbrains)] text-ivory">
                          {run.id}
                        </td>
                        <td className="px-4 py-3">{run.collection}</td>
                        <td className="px-4 py-3 uppercase">{run.backend}</td>
                        <td className="px-4 py-3">
                          {run.passed} / {run.warnings}
                        </td>
                        <td
                          className={`px-4 py-3 font-medium ${
                            run.diff.startsWith("-") ? "text-coral" : "text-accent-emerald"
                          }`}
                        >
                          {run.diff}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="glass-dark rounded-[28px] border border-border-dark p-6">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-gray">Baseline Diff</p>
              <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h2 className="text-2xl font-semibold text-ivory">Scenario and trace comparison</h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-warm-silver">
                    Baselines should show more than a score. The workbench calls out which scenario changed,
                    whether the path slowed down, and whether the runtime or chaos surface shifted underneath it.
                  </p>
                </div>
                <div className="rounded-2xl border border-accent-amber/30 bg-accent-amber/10 px-4 py-3 text-sm text-accent-amber">
                  candidate drift detected
                </div>
              </div>
              <div className="mt-5 overflow-hidden rounded-[24px] border border-border-dark">
                <table className="w-full border-collapse text-left text-sm">
                  <thead className="bg-dark-surface/70 text-stone-gray">
                    <tr>
                      <th className="px-4 py-3 font-medium">Scenario</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">Score</th>
                      <th className="px-4 py-3 font-medium">Traces</th>
                    </tr>
                  </thead>
                  <tbody>
                    {diffRows.map((row) => (
                      <tr key={row.scenario} className="border-t border-border-dark bg-near-black/55 text-warm-silver">
                        <td className="px-4 py-3 text-ivory">{row.scenario}</td>
                        <td className="px-4 py-3">{row.status}</td>
                        <td className="px-4 py-3">{row.score}</td>
                        <td className="px-4 py-3">{row.trace}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

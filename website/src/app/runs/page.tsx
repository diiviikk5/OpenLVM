import Link from "next/link";

export default function RunsPage() {
  return (
    <main className="min-h-screen bg-black text-white px-6 py-12 md:px-10 lg:px-16">
      <div className="mx-auto max-w-4xl">
        <p className="text-xs uppercase tracking-[0.18em] text-white/60">OpenLVM</p>
        <h1 className="mt-3 font-heading italic text-5xl leading-[0.95] tracking-[-2px] md:text-6xl">
          Runs and Results
        </h1>
        <p className="mt-4 max-w-2xl text-sm text-white/80 md:text-base">
          Run creation, baseline compare, trace drilldown, and artifact export all live in the Workbench.
          Use the links below to jump directly into the section you need.
        </p>

        <div className="mt-8 grid gap-3 md:grid-cols-2">
          <Link
            href="/workbench#run-and-compare"
            className="liquid-glass rounded-2xl p-4 no-underline"
          >
            <p className="text-lg font-medium text-white">Run and Compare</p>
            <p className="mt-1 text-sm text-white/75">
              Launch collection runs, choose baselines, and run candidate-vs-baseline comparison.
            </p>
          </Link>
          <Link
            href="/workbench#run-inspection"
            className="liquid-glass rounded-2xl p-4 no-underline"
          >
            <p className="text-lg font-medium text-white">Run Inspection</p>
            <p className="mt-1 text-sm text-white/75">
              Filter by scenario/fork/status, inspect traces, and drill into event payloads.
            </p>
          </Link>
          <Link
            href="/workbench#compare-results"
            className="liquid-glass rounded-2xl p-4 no-underline"
          >
            <p className="text-lg font-medium text-white">Compare Results</p>
            <p className="mt-1 text-sm text-white/75">
              Review score deltas, warning deltas, runtime backend drift, and chaos target changes.
            </p>
          </Link>
          <Link
            href="/workbench#compare-artifacts"
            className="liquid-glass rounded-2xl p-4 no-underline"
          >
            <p className="text-lg font-medium text-white">Saved Artifacts</p>
            <p className="mt-1 text-sm text-white/75">
              Replay prior comparisons, export JSON/CSV, and prune old artifacts.
            </p>
          </Link>
        </div>
      </div>
    </main>
  );
}

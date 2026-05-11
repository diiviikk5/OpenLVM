import Link from "next/link";

const COMMANDS = [
  {
    title: "Preflight + Readiness",
    command: "python -m openlvm.cli arena-preflight --ping --json",
    note: "Check local runtime and Solana integration readiness before running test flows.",
  },
  {
    title: "Workbench Collection Run",
    command: "python -m openlvm.cli collection-run <collection_id> --scenarios 3",
    note: "Execute saved scenarios from one collection with the OpenLVM orchestrator.",
  },
  {
    title: "Save Executable Scenario",
    command:
      "python -m openlvm.cli scenario-save <collection_id> <name> <config_path> <input_text> --execution-command \"python -c \\\"print(123)\\\"\"",
    note: "Store scenario definitions that execute real commands during runs.",
  },
  {
    title: "Arena Scenario Run",
    command:
      "python -m openlvm.cli arena-run --agent-address <pubkey> --scenario <path/to/scenario.json> --wallet-provider embedded",
    note: "Run a Solana Arena scenario with onchain intent metadata generation.",
  },
];

export default function CliPage() {
  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
      <section className="border border-border-dark rounded-xl p-6 bg-dark-surface">
        <h1 className="text-3xl font-semibold text-ivory">CLI Reference</h1>
        <p className="text-warm-silver mt-2">
          Production-focused commands for OpenLVM test runs, saved scenarios, and Solana Arena validation.
        </p>
        <div className="grid gap-3 sm:grid-cols-2 mt-6">
          <Link href="/workbench#quick-run" className="border border-border-dark rounded-lg p-3 no-underline hover:border-olive-gray">
            <p className="text-ivory font-medium">Open Workbench</p>
            <p className="text-sm text-warm-silver mt-1">Run and compare scenarios in the UI.</p>
          </Link>
          <Link href="/solana" className="border border-border-dark rounded-lg p-3 no-underline hover:border-olive-gray">
            <p className="text-ivory font-medium">Solana Integration</p>
            <p className="text-sm text-warm-silver mt-1">Review Arena and agentkit integration flow.</p>
          </Link>
        </div>
      </section>

      <section className="mt-6 space-y-4">
        {COMMANDS.map((row) => (
          <article key={row.title} className="border border-border-dark rounded-xl p-4 bg-near-black">
            <h2 className="text-lg text-ivory font-medium">{row.title}</h2>
            <pre className="mt-3 overflow-x-auto rounded-md border border-border-dark p-3 text-[13px] text-accent-amber">
              <code>{row.command}</code>
            </pre>
            <p className="text-sm text-warm-silver mt-3">{row.note}</p>
          </article>
        ))}
      </section>
    </main>
  );
}

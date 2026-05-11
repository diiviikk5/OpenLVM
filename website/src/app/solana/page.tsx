import Link from "next/link";

const commands = [
  "openlvm arena-readiness",
  "openlvm arena-preflight --ping --json",
  "openlvm arena-run --agent <pubkey> --scenario solana/scenarios/usdc-payment-smoke.json --submit-intent",
  "openlvm arena-submit <arena-run-id> --cluster devnet",
  "openlvm arena-integrations",
  "openlvm release-readiness --json",
];

export default function SolanaPage() {
  return (
    <main className="min-h-screen bg-black text-white px-6 py-12 md:px-10 lg:px-16">
      <div className="mx-auto max-w-4xl">
        <p className="text-xs uppercase tracking-[0.18em] text-white/60">OpenLVM Arena</p>
        <h1 className="mt-3 font-heading italic text-5xl leading-[0.95] tracking-[-2px] md:text-6xl">
          Solana Submission Track
        </h1>
        <p className="mt-4 max-w-2xl text-sm text-white/80 md:text-base">
          This page maps the Solana MVP flow to the real interfaces already in OpenLVM: Workbench arena
          UI, readiness gate commands, onchain intent export, and integration readiness checks.
        </p>

        <div className="mt-8 grid gap-3 md:grid-cols-2">
          <Link href="/workbench#solana-arena" className="liquid-glass rounded-2xl p-4 no-underline">
            <p className="text-lg font-medium text-white">Workbench Arena</p>
            <p className="mt-1 text-sm text-white/75">
              Run arena scenarios, view x402 metadata, export intent, and submit onchain directly.
            </p>
          </Link>
          <Link
            href="https://github.com/diiviikk5/OpenLVM/tree/master/solana"
            target="_blank"
            rel="noreferrer"
            className="liquid-glass rounded-2xl p-4 no-underline"
          >
            <p className="text-lg font-medium text-white">Solana Folder</p>
            <p className="mt-1 text-sm text-white/75">
              Bridge script, scenario payloads, and integration registry used by the arena pipeline.
            </p>
          </Link>
        </div>

        <div className="mt-8 rounded-2xl border border-white/20 bg-white/[0.03] p-5">
          <p className="text-sm font-medium text-white">CLI checklist for final validation</p>
          <ul className="mt-3 space-y-2 text-sm text-white/80">
            {commands.map((command) => (
              <li key={command}>
                <code>{command}</code>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  );
}

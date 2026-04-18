# Solana Agent Arena (MVP Scaffold)

This folder hosts Solana-specific components for OpenLVM Arena.

## Solana CLI setup

Recommended install command:

```bash
curl -fsSL https://www.solana.new/setup.sh | bash
```

After install, restart shell and confirm:

```bash
solana --version
```

## Current MVP state

- `openlvm arena-run --agent <pubkey> --scenario <json>` is available in the Python CLI.
- `openlvm arena-run --agent <pubkey> --scenario <json> --submit-intent` runs and submits in one step.
- `--cluster devnet|testnet|mainnet-beta` can be applied on `arena-run` and `arena-submit` to target a specific network.
- `--require-real-submission` can be added to `arena-run --submit-intent` and `arena-submit` to fail unless submission runs in `agentkit-session` mode.
- `openlvm arena-intent <arena-run-id>` exports the deterministic onchain intent payload.
- `openlvm arena-submit <arena-run-id>` submits that intent through the Solana bridge and stores the submission receipt.
- `openlvm arena-readiness` reports current real-submission readiness and reasons.
- `openlvm arena-readiness --json` prints machine-readable readiness payloads for scripts.
- `openlvm arena-readiness --output-file <path>` writes readiness JSON to a CI artifact file.
- `openlvm arena-preflight` checks whether strict real submission requirements are met.
- `openlvm arena-preflight --ping` performs a live endpoint ping before strict runs.
- `openlvm arena-preflight --json` prints machine-readable readiness output for CI gates.
- `openlvm arena-preflight --allow-ping-warning` allows CI to proceed when ping is flaky but config is correct.
- `openlvm arena-preflight --output-file <path>` writes the preflight JSON payload to a CI artifact file.
- `openlvm ci-gate --json` emits a consolidated CI gate payload combining doctor + arena preflight.
- `openlvm ci-gate --text --summary` prints a single-line gate verdict for compact CI logs.
- `openlvm ci-gate --output-file <path>` writes the consolidated gate JSON to a CI artifact file.
- Workbench `GET /api/workbench/arena/readiness` exposes whether strict real submission is currently possible.
- `openlvm arena-integrations` lists hub integrations and local readiness.
- Arena runs are persisted in the operator store (`arena_runs` table).
- Solana connectivity is routed through `solana/agentkit_bridge.mjs` (Node bridge) with Python fallback.
- Arena runs now include simulated x402 payment settlement metadata and a `sha256` trace commitment.
- Arena runs include an `onchain_intent` payload (`openlvm.arena.intent.v1`) with PDA-seed-ready fields and deterministic intent commitment hash for handoff to a future Solana program/indexer.
- Integration registry lives at `solana/integrations/registry.json`.

## AgentKit session mode

The bridge now supports an API-backed AgentKit session mode.

Required environment variables:

```bash
export OPENLVM_SOLANA_BRIDGE_MODE=agentkit
export OPENLVM_SOLANA_AGENTKIT_API_KEY=...
export OPENLVM_SOLANA_AGENTKIT_ENDPOINT=https://your-agentkit-endpoint
```

Optional:

```bash
export OPENLVM_SOLANA_AGENTKIT_TIMEOUT_MS=15000
```

In this mode, the Node bridge posts `{ command, payload }` JSON to your endpoint with `Authorization: Bearer <api_key>`.
If the endpoint is unavailable or returns an error, Python safely falls back to local stub behavior unless strict real submission is required.

## Next implementation targets

1. Replace stub adapter with real AgentKit connection/session handling.
2. Add x402-backed USDC entry fee and payout settlement hooks.
3. Emit run-result commitments (trace hash + score) to Solana for public verification.
4. Expose Arena run APIs/workbench panels for matchmaking, battles, and replay links.

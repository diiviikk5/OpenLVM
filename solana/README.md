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
- `--require-real-submission` can be added to `arena-run --submit-intent` and `arena-submit` to fail if bridge falls back to stub mode.
- `openlvm arena-intent <arena-run-id>` exports the deterministic onchain intent payload.
- `openlvm arena-submit <arena-run-id>` submits that intent through the Solana bridge and stores the submission receipt.
- Workbench `GET /api/workbench/arena/readiness` exposes whether strict real submission is currently possible.
- `openlvm arena-integrations` lists hub integrations and local readiness.
- Arena runs are persisted in the operator store (`arena_runs` table).
- Solana connectivity is routed through `solana/agentkit_bridge.mjs` (Node bridge) with Python stub fallback.
- Arena runs now include simulated x402 payment settlement metadata and a `sha256` trace commitment.
- Arena runs include an `onchain_intent` payload (`openlvm.arena.intent.v1`) with PDA-seed-ready fields and deterministic intent commitment hash for handoff to a future Solana program/indexer.
- Integration registry lives at `solana/integrations/registry.json`.

## Next implementation targets

1. Replace stub adapter with real AgentKit connection/session handling.
2. Add x402-backed USDC entry fee and payout settlement hooks.
3. Emit run-result commitments (trace hash + score) to Solana for public verification.
4. Expose Arena run APIs/workbench panels for matchmaking, battles, and replay links.

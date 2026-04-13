# Solana Agent Arena (MVP Scaffold)

This folder hosts Solana-specific components for OpenLVM Arena.

## Current MVP state

- `openlvm arena-run --agent <pubkey> --scenario <json>` is available in the Python CLI.
- Arena runs are persisted in the operator store (`arena_runs` table).
- Solana connectivity is currently routed through a lightweight `SolanaAgentKitAdapter` stub for local development.

## Next implementation targets

1. Replace stub adapter with real AgentKit connection/session handling.
2. Add x402-backed USDC entry fee and payout settlement hooks.
3. Emit run-result commitments (trace hash + score) to Solana for public verification.
4. Expose Arena run APIs/workbench panels for matchmaking, battles, and replay links.

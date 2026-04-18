# OpenLVM

OpenLVM is an agent runtime and testing harness built around a Zig core and a Python operator layer.

The current repository state is aimed at getting to a first usable MVP:
- Zig core exports the fork, replay, sandbox, snapshot, and chaos FFI surface.
- Python provides a CLI, run orchestrator, local eval store, MCP entrypoint, and integration adapters.
- The Python layer now has a simulated runtime backend, so you can exercise the product flow before building the Zig core.
- Example configs and tests are included so the package can move into smoke testing once dependencies are installed.

## Current Commands

From `python/` after installing the package:

```powershell
openlvm info
openlvm doctor
openlvm doctor --json
openlvm doctor --output-file .\artifacts\doctor.json
openlvm bench --count 1000
openlvm init
openlvm test ..\examples\swarm.yaml --scenarios 25 --chaos network_delay
openlvm results
openlvm show-run latest
openlvm compare <run-a> <run-b>
openlvm collection-run <collection-id>
openlvm baseline-compare <collection-id> <run-id>
openlvm arena-run --agent <pubkey> --scenario ..\solana\scenarios\usdc-payment-smoke.json
openlvm arena-run --agent <pubkey> --scenario ..\solana\scenarios\usdc-payment-smoke.json --submit-intent
openlvm arena-run --agent <pubkey> --scenario ..\solana\scenarios\usdc-payment-smoke.json --submit-intent --require-real-submission
openlvm arena-run --agent <pubkey> --scenario ..\solana\scenarios\usdc-payment-smoke.json --cluster testnet
openlvm arena-runs
openlvm arena-intent <arena-run-id>
openlvm arena-submit <arena-run-id> --cluster mainnet-beta --require-real-submission
openlvm arena-readiness
openlvm arena-readiness --json
openlvm arena-readiness --output-file .\artifacts\arena-readiness.json
openlvm arena-preflight
openlvm arena-preflight --ping --timeout-ms 5000
openlvm arena-preflight --ping --json
openlvm arena-preflight --ping --allow-ping-warning --json
openlvm arena-preflight --output-file .\artifacts\arena-preflight.json
openlvm ci-gate --json
openlvm ci-gate --text --summary
openlvm ci-gate --output-file .\artifacts\ci-gate.json
openlvm readiness-bundle --artifacts-dir .\artifacts
openlvm readiness-bundle --artifacts-dir .\artifacts --min-readiness-score 85
openlvm readiness-bundle --json
openlvm readiness-plan
openlvm readiness-plan --min-readiness-score 85
openlvm readiness-plan --json
openlvm release-readiness --min-readiness-score 85 --min-integration-ready-percent 70
openlvm release-readiness --json --output-file .\artifacts\release-readiness.json
openlvm arena-integrations
openlvm mcp-serve
```

GitHub Actions now includes `.github/workflows/ci-gate.yml`, which runs these checks and uploads JSON artifacts.

## Local Setup

Prerequisites:
- Zig 0.14.x
- Python 3.10+
- Solana CLI (for Arena flows): `curl -fsSL https://www.solana.new/setup.sh | bash`

Build and install:

```powershell
.\scripts\build.ps1
```

If Zig is not installed yet, you can still run the Python layer in simulated mode. The CLI will fall back automatically when the shared library is unavailable.
The local scripts will use `tools/zig-0.15.2/zig.exe` automatically when it exists.

You can also force the backend explicitly:

```powershell
$env:OPENLVM_RUNTIME = "simulated"
openlvm doctor
```

## Workbench

The Next.js workbench now reads real data from the local OpenLVM stores and can trigger collection runs and baseline compare through API routes.
It includes a Quick Run mode (single input, auto setup), run inspection filters (scenario/fork/status), trace drilldown payload/event inspection, baseline search/sort with quick-select presets, compare history, artifact replay presets, and compare artifact export (`JSON` and `CSV`) for QA workflows.

Run it:

```powershell
npm --prefix website run dev
```

Available API routes:
- `GET /api/workbench/overview`
- `GET /api/workbench/run`
- `POST /api/workbench/run`
- `POST /api/workbench/compare`
- `POST/PATCH/DELETE /api/workbench/workspace`
- `POST/PATCH/DELETE /api/workbench/collection`
- `GET/POST/PATCH/DELETE /api/workbench/scenario`
- `POST /api/workbench/baseline`
- `GET/POST/DELETE /api/workbench/artifact` (save/list/download/delete/prune compare artifacts, including bulk delete via `artifact_ids`)
- `GET/POST/DELETE /api/workbench/member` (workspace member list/upsert/remove with role checks)
- `GET/POST /api/workbench/arena` (list/create Solana Arena MVP runs)
- `GET /api/workbench/arena/readiness` (bridge readiness for strict real submission)
- `GET /api/workbench/arena/[arenaRunId]/intent` (fetch export-ready onchain intent payload for one arena run)
- `POST /api/workbench/arena/[arenaRunId]/submit` (submit stored intent via Solana adapter and persist receipt)
- `GET/POST/DELETE /api/workbench/session` (signed session cookie bootstrap/rotation/clear)

`POST /api/workbench/compare` accepts optional `baseline_ids` to compare one candidate run against multiple saved baselines in a single call.
`GET /api/workbench/run` returns run inspection details plus trace summary for a given `run_id` (or `latest`).

Auth-ready API boundaries:
- Every workbench route now attaches response headers:
  - `x-openlvm-request-id`
  - `x-openlvm-user-id`
  - `x-openlvm-session-id`
  - `x-openlvm-actor-id`
  - `x-openlvm-authenticated`
- Signed `openlvm_session` cookie is now the default identity source.
- Header/cookie identity fallback (`x-openlvm-user-id`, `x-openlvm-session-id`, `openlvm_user_id`, `openlvm_session_id`) is disabled by default and can be re-enabled only with `OPENLVM_ALLOW_HEADER_IDENTITY=1`.
- Mutating API calls use `actor_id=user#session` for audit-safe context propagation.
- `x-openlvm-workspace-id` is now enforced for workbench overview/run/compare routes as a workspace scope boundary.
- Workbench now bootstraps a signed cookie session via `/api/workbench/session`; header-based identity remains as fallback.
- Workspace roles are now enforced for mutating actions (`viewer`, `editor`, `admin`, `owner`) in both API bridge and UI affordances.
- Workbench API routes now map auth/permission/resource errors to `401`/`403`/`404` consistently instead of generic `500`.
- All workbench endpoints except `/api/workbench/session` now require an authenticated signed session and return `401` when missing.
- Bridge-layer stores can be isolated with `OPENLVM_OPERATOR_DB` and `OPENLVM_EVAL_DB` (useful for tests and sandboxed runs).
- Solana Arena MVP runs now attach simulated x402 USDC settlement metadata, deterministic `trace_commitment`, and an exportable `onchain_intent` payload.

Run tests:

```powershell
.\scripts\test.ps1
```

## Repo Layout

- `.github/workflows/`: CI for the Python layer in simulated mode
- `.github/workflows/`: CI for the Python layer in simulated mode and Zig core validation
- `core/`: Zig runtime and FFI exports
- `python/`: Python package, CLI, orchestration, adapters, tests
- `examples/`: starter suite configs
- `scripts/`: local build and test scripts

## Current Gaps

This is not feature-complete yet. The main remaining work is:
- replace simulated orchestration outputs with real agent execution
- tighten Zig/Python integration testing against a built shared library
- deepen MCP and external adapter behavior beyond fallback implementations

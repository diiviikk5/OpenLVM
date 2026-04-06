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
openlvm bench --count 1000
openlvm init
openlvm test ..\examples\swarm.yaml --scenarios 25 --chaos network_delay
openlvm results
openlvm show-run latest
openlvm compare <run-a> <run-b>
openlvm collection-run <collection-id>
openlvm baseline-compare <collection-id> <run-id>
openlvm mcp-serve
```

## Local Setup

Prerequisites:
- Zig 0.14.x
- Python 3.10+

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

Run it:

```powershell
npm --prefix website run dev
```

Available API routes:
- `GET /api/workbench/overview`
- `POST /api/workbench/run`
- `POST /api/workbench/compare`
- `POST /api/workbench/workspace`
- `POST /api/workbench/collection`
- `GET/POST/PATCH/DELETE /api/workbench/scenario`
- `POST /api/workbench/baseline`

Auth-ready API boundaries:
- Every workbench route now attaches response headers:
  - `x-openlvm-request-id`
  - `x-openlvm-user-id`
  - `x-openlvm-authenticated`
- You can pass `x-openlvm-user-id` in requests to scope request identity before full auth/session rollout.

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

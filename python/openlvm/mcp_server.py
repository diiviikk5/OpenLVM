"""MCP server surface for OpenLVM."""

from __future__ import annotations

from pathlib import Path

from .eval_store import EvalStore
from .orchestrator import TestOrchestrator

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - depends on optional package
    FastMCP = None


def build_mcp_server() -> "FastMCP":
    """Create the MCP server instance with OpenLVM tools."""
    if FastMCP is None:
        raise RuntimeError("fastmcp is not installed; install package dependencies to run the MCP server")

    store = EvalStore()
    orchestrator = TestOrchestrator(eval_store=store)
    mcp = FastMCP("openlvm")

    @mcp.tool()
    def fork_and_test(config_path: str, scenarios: int = 100, chaos_mode: str | None = None) -> dict:
        run = orchestrator.run_test_suite(
            Path(config_path),
            scenarios=scenarios,
            chaos_mode=chaos_mode,
        )
        return run.model_dump()

    @mcp.tool()
    def get_eval_results(run_id: str = "latest") -> dict:
        return store.get_run(run_id).model_dump()

    @mcp.tool()
    def compare_runs(run_a: str, run_b: str) -> dict:
        return store.compare_runs(run_a, run_b).model_dump()

    @mcp.resource("openlvm://runs/{run_id}")
    def get_run_resource(run_id: str) -> str:
        return store.get_run(run_id).model_dump_json(indent=2)

    return mcp


def serve() -> None:
    """Start the OpenLVM MCP server."""
    server = build_mcp_server()
    server.run()

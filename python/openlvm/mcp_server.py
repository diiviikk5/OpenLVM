"""MCP server surface for OpenLVM."""

from __future__ import annotations

import json
from pathlib import Path

from .eval_store import EvalStore
from .operator_store import OperatorStore
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
    operator_store = OperatorStore()
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

    @mcp.tool()
    def get_trace_summary(run_id: str = "latest") -> dict:
        return store.get_trace_summary(run_id)

    @mcp.tool()
    def create_workspace(name: str, description: str = "") -> dict:
        return operator_store.create_workspace(name, description).model_dump()

    @mcp.tool()
    def create_collection(workspace_id: str, name: str, description: str = "") -> dict:
        return operator_store.create_collection(workspace_id, name, description).model_dump()

    @mcp.tool()
    def save_collection_scenario(collection_id: str, name: str, config_path: str, input_text: str) -> dict:
        return operator_store.save_scenario(collection_id, name, config_path, input_text).model_dump()

    @mcp.tool()
    def save_baseline(collection_id: str, run_id: str, label: str) -> dict:
        return operator_store.create_baseline(collection_id, run_id, label).model_dump()

    @mcp.tool()
    def inspect_collection(collection_id: str) -> dict:
        return operator_store.get_collection_summary(collection_id)

    @mcp.resource("openlvm://runs/{run_id}")
    def get_run_resource(run_id: str) -> str:
        return store.get_run(run_id).model_dump_json(indent=2)

    @mcp.resource("openlvm://collections/{collection_id}")
    def get_collection_resource(collection_id: str) -> str:
        return json.dumps(operator_store.get_collection_summary(collection_id), indent=2)

    return mcp


def serve() -> None:
    """Start the OpenLVM MCP server."""
    server = build_mcp_server()
    server.run()

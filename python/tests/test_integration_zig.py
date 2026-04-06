from pathlib import Path
import os

import pytest
from typer.testing import CliRunner

from openlvm.cli import app
from openlvm.runtime import OpenLVMRuntime


runner = CliRunner()
zig_dll = Path(__file__).resolve().parents[2] / "core" / "zig-out" / "bin" / "openlvm.dll"


@pytest.mark.skipif(not zig_dll.exists(), reason="Zig runtime library is not built")
def test_cli_test_runs_with_zig_backend(monkeypatch):
    monkeypatch.setenv("OPENLVM_RUNTIME", "zig")
    config_path = Path(__file__).resolve().parents[2] / "examples" / "swarm.yaml"

    result = runner.invoke(app, ["test", str(config_path), "--scenarios", "2", "--chaos", "network_delay"])

    assert result.exit_code == 0
    assert "Run complete:" in result.stdout
    assert "Warnings:" in result.stdout


@pytest.mark.skipif(not zig_dll.exists(), reason="Zig runtime library is not built")
def test_zig_runtime_fork_inherits_parent_and_chaos():
    runtime = OpenLVMRuntime()
    try:
        has_parent_api = getattr(runtime._lib, "_openlvm_has_parent_api", False)
        if not has_parent_api and (os.getenv("OPENLVM_REQUIRE_PARENT_API") or "").strip() == "1":
            raise AssertionError("Zig runtime is missing openlvm_agent_parent export in required mode")
        if not has_parent_api:  # pragma: no cover - compat with old local builds
            pytest.skip("Built runtime is older than parent-introspection API")
        parent_id = runtime.register_agent(0)
        runtime.chaos_add_network_delay(parent_id, 1.0, 300)
        child_id = runtime.fork_agent(parent_id)
        assert runtime.get_parent_agent_id(child_id) == parent_id
        assert runtime.chaos_get_network_delay(child_id) > 0
    finally:
        runtime.close()

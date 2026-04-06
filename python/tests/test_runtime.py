from pathlib import Path

import pytest

from openlvm.runtime import SimulatedOpenLVMRuntime, create_runtime


def test_simulated_runtime_supports_basic_flow():
    runtime = SimulatedOpenLVMRuntime()
    parent = runtime.register_agent(0)
    runtime.chaos_add_network_delay(parent, 1.0, 250)
    children = runtime.fork_many(parent, 3)

    assert len(children) == 3
    assert runtime.get_active_agent_count() == 4
    assert runtime.chaos_get_network_delay(parent) == 250
    assert runtime.get_parent_agent_id(children[0]) == parent
    assert runtime.chaos_get_network_delay(children[0]) == 250
    assert runtime.version().endswith("-sim")


def test_create_runtime_falls_back_to_simulated_without_library(monkeypatch):
    monkeypatch.delenv("OPENLVM_RUNTIME", raising=False)
    monkeypatch.setattr("openlvm.runtime.OpenLVMRuntime", lambda: (_ for _ in ()).throw(FileNotFoundError("missing")))
    runtime = create_runtime()
    assert runtime.backend == "simulated"


def test_create_runtime_respects_env_override(monkeypatch):
    monkeypatch.setenv("OPENLVM_RUNTIME", "simulated")
    runtime = create_runtime()
    assert runtime.backend == "simulated"


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "core" / "zig-out" / "bin" / "openlvm.dll").exists(),
    reason="Zig runtime library is not built",
)
def test_create_runtime_uses_zig_backend_when_library_exists(monkeypatch):
    monkeypatch.setenv("OPENLVM_RUNTIME", "zig")
    runtime = create_runtime()
    assert runtime.backend == "zig"

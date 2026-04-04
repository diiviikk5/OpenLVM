from openlvm.runtime import SimulatedOpenLVMRuntime, create_runtime


def test_simulated_runtime_supports_basic_flow():
    runtime = SimulatedOpenLVMRuntime()
    parent = runtime.register_agent(0)
    children = runtime.fork_many(parent, 3)
    runtime.chaos_add_network_delay(parent, 1.0, 250)

    assert len(children) == 3
    assert runtime.get_active_agent_count() == 4
    assert runtime.chaos_get_network_delay(parent) == 250
    assert runtime.version().endswith("-sim")


def test_create_runtime_falls_back_to_simulated_without_library(monkeypatch):
    monkeypatch.setattr("openlvm.runtime.OpenLVMRuntime", lambda: (_ for _ in ()).throw(FileNotFoundError("missing")))
    runtime = create_runtime()
    assert runtime.backend == "simulated"


def test_create_runtime_respects_env_override(monkeypatch):
    monkeypatch.setenv("OPENLVM_RUNTIME", "simulated")
    runtime = create_runtime()
    assert runtime.backend == "simulated"

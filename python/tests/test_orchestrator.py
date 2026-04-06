from pathlib import Path

from openlvm.eval_store import EvalStore
from openlvm.orchestrator import TestOrchestrator
from openlvm.runtime import SimulatedOpenLVMRuntime


class FakeRuntime:
    def __init__(self):
        self.next_id = 1
        self.network_delay = 0

    def register_agent(self, caps_bitmask: int) -> int:
        agent_id = self.next_id
        self.next_id += 1
        return agent_id

    def fork_many(self, agent_id: int, count: int) -> list[int]:
        return list(range(100, 100 + count))

    def chaos_add_network_delay(self, agent_id: int, probability: float, delay_ms: int) -> None:
        self.network_delay = delay_ms

    def chaos_add_hallucination(self, agent_id: int, probability: float, corruption_rate: float) -> None:
        return None

    def chaos_get_network_delay(self, agent_id: int) -> int:
        return self.network_delay


def test_orchestrator_runs_suite_and_stores_results(tmp_path):
    runtime = FakeRuntime()
    store = EvalStore(tmp_path / "eval_store.db")
    orchestrator = TestOrchestrator(runtime=runtime, eval_store=store)

    config_path = Path(__file__).resolve().parents[2] / "examples" / "swarm.yaml"
    run = orchestrator.run_test_suite(config_path, scenarios=3, chaos_mode="network_delay")

    assert run.scenarios_executed == 3
    assert run.agent_count == 3
    assert run.summary["passed"] + run.summary["warnings"] == 3
    assert store.get_run(run.run_id).run_id == run.run_id


def test_orchestrator_records_runtime_backend_with_simulation(tmp_path):
    store = EvalStore(tmp_path / "eval_store.db")
    orchestrator = TestOrchestrator(runtime=SimulatedOpenLVMRuntime(), eval_store=store)
    config_path = Path(__file__).resolve().parents[2] / "examples" / "swarm.yaml"

    run = orchestrator.run_test_suite(config_path, scenarios=2)

    assert run.metadata["runtime_backend"] == "simulated"


def test_orchestrator_records_targeted_chaos_effects(tmp_path):
    store = EvalStore(tmp_path / "eval_store.db")
    orchestrator = TestOrchestrator(runtime=SimulatedOpenLVMRuntime(), eval_store=store)
    config_path = Path(__file__).resolve().parents[2] / "examples" / "swarm.yaml"

    run = orchestrator.run_test_suite(config_path, scenarios=1, chaos_mode="network_delay")

    result = run.results[0]
    assert "executor" in result.chaos_effects
    assert result.chaos_effects["executor"]["type"] == "network_delay"
    assert result.chaos_effects["executor"]["delay_ms"] >= 0
    assert run.metadata["chaos_targets"] == ["executor"]

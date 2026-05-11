from pathlib import Path
import sys

from openlvm.eval_store import EvalStore
from openlvm.models import AgentConfig, ScenarioConfig, TestSuiteConfig
from openlvm.operator_store import OperatorStore
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

    def get_parent_agent_id(self, agent_id: int) -> int | None:
        if agent_id >= 100:
            return 1
        return None

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
    assert run.results[0].fork_parent_id == 1
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
    assert "__fork__" in result.chaos_effects
    assert "executor" in result.chaos_effects
    assert result.chaos_effects["executor"]["type"] == "network_delay"
    assert result.chaos_effects["executor"]["delay_ms"] >= 0
    assert run.metadata["chaos_targets"] == ["executor"]


def test_orchestrator_runs_saved_collection(tmp_path):
    eval_store = EvalStore(tmp_path / "eval_store.db")
    operator_store = OperatorStore(tmp_path / "operator_store.db")
    orchestrator = TestOrchestrator(
        runtime=SimulatedOpenLVMRuntime(),
        eval_store=eval_store,
        operator_store=operator_store,
    )
    config_path = Path(__file__).resolve().parents[2] / "examples" / "swarm.yaml"

    workspace = operator_store.create_workspace("Team A")
    collection = operator_store.create_collection(workspace.workspace_id, "Support")
    operator_store.save_scenario(collection.collection_id, "cancel-flow", str(config_path), "Cancel my plan")
    operator_store.save_scenario(collection.collection_id, "refund-flow", str(config_path), "Refund last invoice")

    run = orchestrator.run_collection(collection.collection_id)

    assert run.scenarios_executed == 2
    assert run.metadata["collection"]["collection_id"] == collection.collection_id
    assert run.metadata["collection"]["collection_name"] == "Support"
    assert eval_store.get_run(run.run_id).run_id == run.run_id


def test_orchestrator_run_collection_executes_saved_scenario_command(tmp_path):
    eval_store = EvalStore(tmp_path / "eval_store.db")
    operator_store = OperatorStore(tmp_path / "operator_store.db")
    orchestrator = TestOrchestrator(
        runtime=SimulatedOpenLVMRuntime(),
        eval_store=eval_store,
        operator_store=operator_store,
    )
    config_path = Path(__file__).resolve().parents[2] / "examples" / "swarm.yaml"

    workspace = operator_store.create_workspace("Team A")
    collection = operator_store.create_collection(workspace.workspace_id, "Support")
    operator_store.save_scenario(
        collection.collection_id,
        "exec-flow",
        str(config_path),
        "run command",
        execution_command=f'"{sys.executable}" -c "print(\'collection-exec\')"',
        execution_timeout_ms=12000,
        success_exit_codes_json="[0]",
    )

    run = orchestrator.run_collection(collection.collection_id)
    result = run.results[0]

    assert result.status == "passed"
    assert result.execution["success"] is True
    assert "collection-exec" in result.execution["stdout"]


def test_orchestrator_executes_scenario_command(tmp_path):
    orchestrator = TestOrchestrator(
        runtime=SimulatedOpenLVMRuntime(),
        eval_store=EvalStore(tmp_path / "eval_store.db"),
    )
    config = TestSuiteConfig(
        name="command-suite",
        agents={
            "runner": AgentConfig(entry="agents/runner.py", capabilities=["llm_call"]),
        },
        scenarios={
            "exec_pass": ScenarioConfig(
                input="run command",
                execution_command=f'"{sys.executable}" -c "print(\'openlvm-real-exec\')"',
            )
        },
    )

    run = orchestrator.run_test_suite(config, scenarios=1)

    result = run.results[0]
    assert result.status == "passed"
    assert result.execution["success"] is True
    assert "openlvm-real-exec" in result.execution["stdout"]
    assert result.metrics["execution_exit_code"] == 0.0


def test_orchestrator_marks_failed_when_scenario_command_fails(tmp_path):
    orchestrator = TestOrchestrator(
        runtime=SimulatedOpenLVMRuntime(),
        eval_store=EvalStore(tmp_path / "eval_store.db"),
    )
    config = TestSuiteConfig(
        name="command-suite",
        agents={
            "runner": AgentConfig(entry="agents/runner.py", capabilities=["llm_call"]),
        },
        scenarios={
            "exec_fail": ScenarioConfig(
                input="run command",
                execution_command=f'"{sys.executable}" -c "import sys; sys.exit(3)"',
            )
        },
    )

    run = orchestrator.run_test_suite(config, scenarios=1)

    result = run.results[0]
    assert result.status == "failed"
    assert run.summary["failed"] == 1
    assert result.execution["success"] is False
    assert any("exited with code 3" in warning for warning in result.warnings)

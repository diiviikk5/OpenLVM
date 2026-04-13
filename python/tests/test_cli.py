from pathlib import Path

from typer.testing import CliRunner

from openlvm.cli import app
from openlvm.eval_store import EvalStore
from openlvm.models import EvalRun, ScenarioRunResult
from openlvm.operator_store import OperatorStore


runner = CliRunner()


def test_init_writes_starter_config(tmp_path):
    output = tmp_path / "openlvm.yaml"
    result = runner.invoke(app, ["init", str(output)])
    assert result.exit_code == 0
    assert output.exists()
    assert "customer-support-swarm" in output.read_text(encoding="utf-8")


def test_show_run_json_outputs_payload(tmp_path, monkeypatch):
    store = EvalStore(tmp_path / "eval_store.db")
    store.store_run(
        EvalRun(
            run_id="run-test",
            suite_name="demo",
            suite_version="1.0",
            config_path=str(Path("examples/swarm.yaml")),
            started_at="2026-04-04T00:00:00+00:00",
            completed_at="2026-04-04T00:00:01+00:00",
            scenarios_requested=1,
            scenarios_executed=1,
            summary={"passed": 1, "warnings": 0, "failed": 0},
        )
    )

    monkeypatch.setattr("openlvm.cli.EvalStore", lambda: store)
    result = runner.invoke(app, ["show-run", "run-test", "--json"])
    assert result.exit_code == 0
    assert '"run_id":"run-test"' in result.stdout or '"run_id": "run-test"' in result.stdout


def test_doctor_reports_runtime(monkeypatch):
    monkeypatch.setenv("OPENLVM_RUNTIME", "simulated")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "simulated" in result.stdout


def test_bench_runs_with_simulated_runtime(monkeypatch):
    monkeypatch.setenv("OPENLVM_RUNTIME", "simulated")
    result = runner.invoke(app, ["bench", "--count", "5"])
    assert result.exit_code == 0
    assert "Forks: 5" in result.stdout


def test_workspace_and_collection_commands(tmp_path, monkeypatch):
    store = OperatorStore(tmp_path / "operator_store.db")
    monkeypatch.setattr("openlvm.cli.OperatorStore", lambda: store)

    workspace_result = runner.invoke(app, ["workspace-create", "Team A"])
    assert workspace_result.exit_code == 0

    workspace_id = store.list_workspaces()[0].workspace_id
    collection_result = runner.invoke(app, ["collection-create", workspace_id, "Support"])
    assert collection_result.exit_code == 0
    assert store.list_collections(workspace_id)[0].name == "Support"


def test_collection_inspect_and_baseline_compare(tmp_path, monkeypatch):
    store = OperatorStore(tmp_path / "operator_store.db")
    eval_store = EvalStore(tmp_path / "eval_store.db")
    monkeypatch.setattr("openlvm.cli.OperatorStore", lambda: store)
    monkeypatch.setattr("openlvm.cli.EvalStore", lambda: eval_store)

    workspace = store.create_workspace("Team A")
    collection = store.create_collection(workspace.workspace_id, "Support")
    store.save_scenario(collection.collection_id, "cancel-flow", "examples/swarm.yaml", "Help me cancel")

    eval_store.store_run(
        EvalRun(
            run_id="run-a",
            suite_name="demo",
            suite_version="1.0",
            config_path="examples/swarm.yaml",
            started_at="2026-04-04T00:00:00+00:00",
            completed_at="2026-04-04T00:00:01+00:00",
            scenarios_requested=1,
            scenarios_executed=1,
            summary={"passed": 1, "warnings": 0, "failed": 0, "warning_events": 0},
            results=[
                ScenarioRunResult(
                    name="cancel-flow",
                    fork_id=1,
                    input="Help me cancel",
                    status="passed",
                    score=0.95,
                )
            ],
            metadata={"traces": [{}], "runtime_backend": "simulated", "chaos_targets": []},
        )
    )
    eval_store.store_run(
        EvalRun(
            run_id="run-b",
            suite_name="demo",
            suite_version="1.0",
            config_path="examples/swarm.yaml",
            started_at="2026-04-04T00:00:02+00:00",
            completed_at="2026-04-04T00:00:03+00:00",
            scenarios_requested=1,
            scenarios_executed=1,
            summary={"passed": 0, "warnings": 1, "failed": 0, "warning_events": 1},
            results=[
                ScenarioRunResult(
                    name="cancel-flow",
                    fork_id=2,
                    input="Help me cancel",
                    status="warning",
                    score=0.70,
                    network_delay_ms=300,
                    warnings=["network delay injected on executor: 300ms"],
                )
            ],
            metadata={"traces": [{}, {}], "runtime_backend": "zig", "chaos_targets": ["executor"]},
        )
    )
    store.create_baseline(collection.collection_id, "run-a", "stable")

    inspect_result = runner.invoke(app, ["collection-inspect", collection.collection_id])
    assert inspect_result.exit_code == 0
    assert "Collection Scenarios" in inspect_result.stdout

    compare_result = runner.invoke(app, ["baseline-compare", collection.collection_id, "run-b"])
    assert compare_result.exit_code == 0
    assert "Baseline Compare" in compare_result.stdout
    assert "Scenario Diffs" in compare_result.stdout
    assert "Runtime backend changed" in compare_result.stdout


def test_collection_run_command(tmp_path, monkeypatch):
    store = OperatorStore(tmp_path / "operator_store.db")
    eval_store = EvalStore(tmp_path / "eval_store.db")
    monkeypatch.setattr("openlvm.cli.OperatorStore", lambda: store)

    workspace = store.create_workspace("Team A")
    collection = store.create_collection(workspace.workspace_id, "Support")

    config_path = Path(__file__).resolve().parents[2] / "examples" / "swarm.yaml"
    store.save_scenario(collection.collection_id, "cancel-flow", str(config_path), "Cancel my plan")

    class DummyOrchestrator:
        def run_collection(self, collection_id, scenarios=None, chaos_mode=None):
            run = EvalRun(
                run_id="run-collection",
                suite_name="demo:Support",
                suite_version="1.0",
                config_path=str(config_path),
                started_at="2026-04-04T00:00:00+00:00",
                completed_at="2026-04-04T00:00:01+00:00",
                scenarios_requested=scenarios or 1,
                scenarios_executed=1,
                chaos_mode=chaos_mode,
                summary={"passed": 1, "warnings": 0, "failed": 0},
                metadata={
                    "collection": {
                        "collection_id": collection_id,
                        "workspace_id": workspace.workspace_id,
                        "collection_name": "Support",
                    }
                },
            )
            eval_store.store_run(run)
            return run

    monkeypatch.setattr("openlvm.cli.TestOrchestrator", lambda: DummyOrchestrator())
    result = runner.invoke(app, ["collection-run", collection.collection_id, "--scenarios", "1"])
    assert result.exit_code == 0
    assert "Collection run complete" in result.stdout
    assert "Support" in result.stdout


def test_arena_intent_command_outputs_json(tmp_path, monkeypatch):
    store = OperatorStore(tmp_path / "operator_store.db")
    run = store.create_arena_run(
        "AgentPubKey111",
        "scenario-usdc-transfer",
        0.88,
        "passed",
        metadata={
            "trace_commitment": "sha256:test",
            "onchain_intent": {
                "schema": "openlvm.arena.intent.v1",
                "intent_commitment": "sha256:intent",
            },
        },
        actor_id="arena#test",
    )
    monkeypatch.setattr("openlvm.cli.OperatorStore", lambda: store)

    result = runner.invoke(app, ["arena-intent", run.arena_run_id, "--json"])
    assert result.exit_code == 0
    assert '"arena_run_id"' in result.stdout
    assert "openlvm.arena.intent.v1" in result.stdout


def test_arena_submit_command_persists_submission(tmp_path, monkeypatch):
    store = OperatorStore(tmp_path / "operator_store.db")
    run = store.create_arena_run(
        "AgentPubKey111",
        "scenario-usdc-transfer",
        0.88,
        "passed",
        metadata={
            "trace_commitment": "sha256:test",
            "onchain_intent": {
                "schema": "openlvm.arena.intent.v1",
                "cluster": "devnet",
                "intent_commitment": "sha256:intent",
            },
        },
        actor_id="arena#test",
    )
    monkeypatch.setattr("openlvm.cli.OperatorStore", lambda: store)
    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "stub")

    result = runner.invoke(app, ["arena-submit", run.arena_run_id])
    assert result.exit_code == 0
    assert "Arena intent submitted" in result.stdout
    updated = store.get_arena_run(run.arena_run_id)
    assert updated.metadata["onchain_submission"]["signature"]


def test_arena_submit_command_is_idempotent(tmp_path, monkeypatch):
    store = OperatorStore(tmp_path / "operator_store.db")
    run = store.create_arena_run(
        "AgentPubKey111",
        "scenario-usdc-transfer",
        0.88,
        "passed",
        metadata={
            "trace_commitment": "sha256:test",
            "onchain_intent": {
                "schema": "openlvm.arena.intent.v1",
                "cluster": "devnet",
                "intent_commitment": "sha256:intent",
            },
            "onchain_submission": {
                "submission_status": "simulated_confirmed",
                "signature": "sig-1",
                "explorer_url": "https://explorer.solana.com/tx/sig-1?cluster=devnet",
            },
        },
        actor_id="arena#test",
    )
    monkeypatch.setattr("openlvm.cli.OperatorStore", lambda: store)

    result = runner.invoke(app, ["arena-submit", run.arena_run_id])
    assert result.exit_code == 0
    assert "already submitted" in result.stdout.lower()

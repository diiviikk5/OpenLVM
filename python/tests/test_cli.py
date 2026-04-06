from pathlib import Path

from typer.testing import CliRunner

from openlvm.cli import app
from openlvm.eval_store import EvalStore
from openlvm.models import EvalRun
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
            summary={"passed": 1, "warnings": 0, "failed": 0},
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
            summary={"passed": 0, "warnings": 1, "failed": 0},
        )
    )
    store.create_baseline(collection.collection_id, "run-a", "stable")

    inspect_result = runner.invoke(app, ["collection-inspect", collection.collection_id])
    assert inspect_result.exit_code == 0
    assert "Collection Scenarios" in inspect_result.stdout

    compare_result = runner.invoke(app, ["baseline-compare", collection.collection_id, "run-b"])
    assert compare_result.exit_code == 0
    assert "Baseline Compare" in compare_result.stdout

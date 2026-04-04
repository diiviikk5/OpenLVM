from pathlib import Path

from typer.testing import CliRunner

from openlvm.cli import app
from openlvm.eval_store import EvalStore
from openlvm.models import EvalRun


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

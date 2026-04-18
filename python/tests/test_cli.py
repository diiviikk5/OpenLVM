import json
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


def test_doctor_json_outputs_payload(monkeypatch):
    monkeypatch.setenv("OPENLVM_RUNTIME", "simulated")
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "checks" in payload
    assert isinstance(payload["checks"], list)
    assert isinstance(payload["missing"], list)
    runtime_mode = next(check for check in payload["checks"] if check["name"] == "runtime mode")
    assert runtime_mode["detail"] == "simulated"


def test_doctor_output_file_writes_json(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLVM_RUNTIME", "simulated")
    output_file = tmp_path / "doctor.json"
    result = runner.invoke(app, ["doctor", "--output-file", str(output_file)])
    assert result.exit_code == 0
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert "checks" in payload
    assert "ok" in payload


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
    assert updated.metadata["onchain_submission"]["cluster"] == "devnet"


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


def test_arena_run_can_auto_submit_intent(tmp_path, monkeypatch):
    store = OperatorStore(tmp_path / "operator_store.db")
    scenario_path = tmp_path / "arena-scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "id": "arena-auto-submit",
                "checks": ["wallet", "payment"],
                "entry_fee_usdc": 0.05,
                "arena_opponent": "arena-pool",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("openlvm.cli.OperatorStore", lambda: store)
    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "stub")

    result = runner.invoke(
        app,
        [
            "arena-run",
            "--agent",
            "AgentPubKeyAuto111",
            "--scenario",
            str(scenario_path),
            "--cluster",
            "testnet",
            "--submit-intent",
        ],
    )
    assert result.exit_code == 0
    rows = store.list_arena_runs(limit=1)
    assert rows[0].metadata["onchain_submission"]["signature"]
    assert rows[0].metadata["onchain_intent"]["cluster"] == "testnet"


def test_arena_run_require_real_submission_fails_on_stub(tmp_path, monkeypatch):
    store = OperatorStore(tmp_path / "operator_store.db")
    scenario_path = tmp_path / "arena-scenario-strict.json"
    scenario_path.write_text(
        json.dumps({"id": "arena-strict", "checks": ["wallet"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr("openlvm.cli.OperatorStore", lambda: store)
    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "stub")

    result = runner.invoke(
        app,
        [
            "arena-run",
            "--agent",
            "AgentPubKeyStrict111",
            "--scenario",
            str(scenario_path),
            "--submit-intent",
            "--require-real-submission",
        ],
    )
    assert result.exit_code == 1
    assert "agentkit session mode" in result.stdout.lower()


def test_arena_submit_require_real_submission_fails_on_node_bridge_mode(tmp_path, monkeypatch):
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

    class FakeAdapter:
        bridge_mode = "node-bridge"

        @staticmethod
        def is_real_submission_mode(mode):
            return mode == "agentkit-session"

        def submit_onchain_intent(self, *, intent_commitment, cluster):
            return {
                "submission_status": "simulated_confirmed",
                "signature": "sig-node-1",
                "cluster": cluster,
                "explorer_url": f"https://explorer.solana.com/tx/sig-node-1?cluster={cluster}",
                "metadata": {"adapter_mode": "node-bridge"},
            }

    monkeypatch.setattr("openlvm.cli.SolanaAgentKitAdapter", FakeAdapter)

    result = runner.invoke(app, ["arena-submit", run.arena_run_id, "--require-real-submission"])
    assert result.exit_code == 1
    assert "agentkit session mode" in result.stdout.lower()


def test_arena_preflight_fails_when_agentkit_config_missing(monkeypatch):
    monkeypatch.delenv("OPENLVM_SOLANA_BRIDGE_MODE", raising=False)
    monkeypatch.delenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", raising=False)
    monkeypatch.delenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", raising=False)

    result = runner.invoke(app, ["arena-preflight"])
    assert result.exit_code == 1
    assert "Arena Preflight" in result.stdout


def test_arena_preflight_passes_with_agentkit_env(monkeypatch):
    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "agentkit")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "test-key")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "https://example.com/agentkit")

    result = runner.invoke(app, ["arena-preflight"])
    assert result.exit_code == 0
    assert "agentkit-session" in result.stdout


def test_arena_preflight_ping_uses_endpoint(monkeypatch):
    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "agentkit")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "test-key")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "https://example.com/agentkit")
    monkeypatch.setattr("openlvm.cli._agentkit_ping", lambda endpoint, api_key, timeout_ms=5000: (True, "http 200"))

    result = runner.invoke(app, ["arena-preflight", "--ping"])
    assert result.exit_code == 0
    assert "live ping" in result.stdout.lower()


def test_arena_preflight_json_failure_shape(monkeypatch):
    monkeypatch.delenv("OPENLVM_SOLANA_BRIDGE_MODE", raising=False)
    monkeypatch.delenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", raising=False)
    monkeypatch.delenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", raising=False)

    result = runner.invoke(app, ["arena-preflight", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["real_submission_ready"] is False
    assert isinstance(payload["checks"], list)
    assert any(check["name"] == "resolved mode" for check in payload["checks"])


def test_arena_preflight_json_success_shape(monkeypatch):
    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "agentkit")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "test-key")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "https://example.com/agentkit")
    monkeypatch.setattr("openlvm.cli._agentkit_ping", lambda endpoint, api_key, timeout_ms=5000: (True, "http 200"))

    result = runner.invoke(app, ["arena-preflight", "--ping", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["real_submission_ready"] is True
    assert payload["ping_requested"] is True
    assert payload["ping_ok"] is True
    assert payload["ping_warning_enforced"] is True
    assert any(check["name"] == "live ping" and check["status"] == "ok" for check in payload["checks"])


def test_arena_preflight_ping_failure_is_nonzero_by_default(monkeypatch):
    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "agentkit")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "test-key")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "https://example.com/agentkit")
    monkeypatch.setattr(
        "openlvm.cli._agentkit_ping",
        lambda endpoint, api_key, timeout_ms=5000: (False, "network error: refused"),
    )

    result = runner.invoke(app, ["arena-preflight", "--ping"])
    assert result.exit_code == 1


def test_arena_preflight_ping_failure_can_be_allowed(monkeypatch):
    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "agentkit")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "test-key")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "https://example.com/agentkit")
    monkeypatch.setattr(
        "openlvm.cli._agentkit_ping",
        lambda endpoint, api_key, timeout_ms=5000: (False, "network error: refused"),
    )

    result = runner.invoke(app, ["arena-preflight", "--ping", "--allow-ping-warning", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["ping_ok"] is False
    assert payload["ping_warning_enforced"] is False


def test_arena_preflight_output_file_writes_json(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLVM_SOLANA_BRIDGE_MODE", "agentkit")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "test-key")
    monkeypatch.setenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "https://example.com/agentkit")
    output_file = tmp_path / "preflight.json"
    result = runner.invoke(app, ["arena-preflight", "--output-file", str(output_file)])
    assert result.exit_code == 0
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["real_submission_ready"] is True
    assert isinstance(payload["checks"], list)


def test_ci_gate_json_success(monkeypatch):
    monkeypatch.setattr(
        "openlvm.cli._doctor_payload",
        lambda: {"ok": True, "backend": "simulated", "checks": [], "missing": []},
    )
    monkeypatch.setattr(
        "openlvm.cli._arena_preflight_payload",
        lambda **kwargs: {"ok": True, "checks": [], "ping_requested": kwargs.get("ping", True)},
    )
    result = runner.invoke(app, ["ci-gate", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["doctor"]["ok"] is True
    assert payload["arena_preflight"]["ok"] is True


def test_ci_gate_json_failure(monkeypatch):
    monkeypatch.setattr(
        "openlvm.cli._doctor_payload",
        lambda: {"ok": True, "backend": "simulated", "checks": [], "missing": []},
    )
    monkeypatch.setattr(
        "openlvm.cli._arena_preflight_payload",
        lambda **kwargs: {"ok": False, "checks": [], "ping_requested": kwargs.get("ping", True)},
    )
    result = runner.invoke(app, ["ci-gate", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["doctor"]["ok"] is True
    assert payload["arena_preflight"]["ok"] is False


def test_ci_gate_text_output(monkeypatch):
    monkeypatch.setattr(
        "openlvm.cli._doctor_payload",
        lambda: {"ok": True, "backend": "simulated", "checks": [], "missing": []},
    )
    monkeypatch.setattr(
        "openlvm.cli._arena_preflight_payload",
        lambda **kwargs: {"ok": True, "checks": [], "ping_requested": kwargs.get("ping", True)},
    )
    result = runner.invoke(app, ["ci-gate", "--text"])
    assert result.exit_code == 0
    assert "OpenLVM CI Gate" in result.stdout


def test_ci_gate_summary_success(monkeypatch):
    monkeypatch.setattr(
        "openlvm.cli._doctor_payload",
        lambda: {"ok": True, "backend": "simulated", "checks": [], "missing": []},
    )
    monkeypatch.setattr(
        "openlvm.cli._arena_preflight_payload",
        lambda **kwargs: {"ok": True, "checks": [], "ping_requested": True, "ping_ok": True},
    )
    result = runner.invoke(app, ["ci-gate", "--text", "--summary"])
    assert result.exit_code == 0
    assert "ci-gate: ok" in result.stdout
    assert "| ping=ok" in result.stdout


def test_ci_gate_summary_failure(monkeypatch):
    monkeypatch.setattr(
        "openlvm.cli._doctor_payload",
        lambda: {"ok": False, "backend": "simulated", "checks": [], "missing": ["zig"]},
    )
    monkeypatch.setattr(
        "openlvm.cli._arena_preflight_payload",
        lambda **kwargs: {"ok": True, "checks": [], "ping_requested": False},
    )
    result = runner.invoke(app, ["ci-gate", "--text", "--summary"])
    assert result.exit_code == 1
    assert "ci-gate: fail" in result.stdout


def test_ci_gate_json_contains_summary(monkeypatch):
    monkeypatch.setattr(
        "openlvm.cli._doctor_payload",
        lambda: {"ok": True, "backend": "simulated", "checks": [], "missing": []},
    )
    monkeypatch.setattr(
        "openlvm.cli._arena_preflight_payload",
        lambda **kwargs: {"ok": True, "checks": [], "ping_requested": False},
    )
    result = runner.invoke(app, ["ci-gate", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "summary" in payload
    assert payload["summary"].startswith("ci-gate: ok")


def test_ci_gate_output_file_writes_json(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "openlvm.cli._doctor_payload",
        lambda: {"ok": True, "backend": "simulated", "checks": [], "missing": []},
    )
    monkeypatch.setattr(
        "openlvm.cli._arena_preflight_payload",
        lambda **kwargs: {"ok": True, "checks": [], "ping_requested": False},
    )
    output_file = tmp_path / "ci-gate.json"
    result = runner.invoke(app, ["ci-gate", "--json", "--output-file", str(output_file)])
    assert result.exit_code == 0
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert "doctor" in payload
    assert "arena_preflight" in payload

import json
import os
import importlib.util
from pathlib import Path
import pytest


def _load_bridge_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "website" / "scripts" / "workbench_api.py"
    spec = importlib.util.spec_from_file_location("workbench_api_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._bootstrap()
    return module


def _run_bridge(module, command: str, args: list[str]) -> dict:
    handler = getattr(module, f"_{command}")
    payload = handler(args)
    text = json.dumps(payload)
    parsed = json.loads(text)
    assert "error" not in parsed, parsed
    return parsed


def test_workbench_bridge_uses_isolated_store_paths(tmp_path):
    operator_db = tmp_path / "operator.db"
    eval_db = tmp_path / "eval.db"
    env = {
        **os.environ,
        "OPENLVM_OPERATOR_DB": str(operator_db),
        "OPENLVM_EVAL_DB": str(eval_db),
        "OPENLVM_RUNTIME": "simulated",
    }
    old_env = dict(os.environ)
    os.environ.update(env)
    module = _load_bridge_module()

    try:
        actor_id = "alice#sess1"
        workspace = _run_bridge(module, "create_workspace", ["Team Test", actor_id])
        collection = _run_bridge(
            module,
            "create_collection",
            [workspace["workspace_id"], "Collection A", actor_id],
        )
        _run_bridge(
            module,
            "save_scenario",
            [
                collection["collection_id"],
                "scenario-a",
                "examples/swarm.yaml",
                "hello from isolated bridge test",
                actor_id,
                "",
                "30000",
                "",
                "{}",
                "[0]",
            ],
        )

        run = _run_bridge(
            module,
            "run_collection",
            [collection["collection_id"], "1", "", "", actor_id],
        )
        assert run["run_id"].startswith("run-")
        _run_bridge(
            module,
            "save_baseline",
            [collection["collection_id"], run["run_id"], "seed-baseline", actor_id],
        )
        compare = _run_bridge(
            module,
            "compare_baseline",
            [collection["collection_id"], run["run_id"], "", "", actor_id],
        )
        assert compare["candidate_run_id"] == run["run_id"]
        assert compare["diffs"], "expected at least one baseline diff"

        overview = _run_bridge(module, "overview", ["", actor_id])
        assert any(ws["workspace_id"] == workspace["workspace_id"] for ws in overview["workspaces"])
        assert any(col["collection_id"] == collection["collection_id"] for col in overview["collections"])
        assert operator_db.exists(), "operator db path from env was not used"
        assert eval_db.exists(), "eval db path from env was not used"
        readiness = _run_bridge(module, "arena_readiness", [actor_id])
        assert isinstance(readiness["adapter_mode"], str)
        assert isinstance(readiness["can_real_submission"], bool)
        assert isinstance(readiness["reasons"], list)
        assert isinstance(readiness["issues"], list)
        assert isinstance(readiness["next_actions"], list)
        assert isinstance(readiness["readiness_score"], int)
        readiness_plan = _run_bridge(module, "arena_readiness_plan", [actor_id])
        assert isinstance(readiness_plan["action_plan"], list)
        assert isinstance(readiness_plan["readiness_score"], int)
        release_readiness = _run_bridge(module, "arena_release_readiness", [actor_id, "false", "5000", "true", "80", "70"])
        assert isinstance(release_readiness["decision"], str)
        assert isinstance(release_readiness["summary"], dict)
        assert isinstance(release_readiness["blockers"], list)
        os.environ["OPENLVM_SOLANA_BRIDGE_MODE"] = "agentkit"
        os.environ.pop("OPENLVM_SOLANA_AGENTKIT_API_KEY", None)
        os.environ.pop("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", None)
        readiness_missing = _run_bridge(module, "arena_readiness", [actor_id])
        assert readiness_missing["can_real_submission"] is False
        assert "OPENLVM_SOLANA_AGENTKIT_API_KEY is missing" in readiness_missing["reasons"]
        assert "OPENLVM_SOLANA_AGENTKIT_ENDPOINT is missing" in readiness_missing["reasons"]

        scenario_json = tmp_path / "arena-scenario.json"
        scenario_json.write_text(
            json.dumps(
                {
                    "id": "arena-smoke",
                    "checks": ["wallet", "payment"],
                    "entry_fee_usdc": 0.07,
                    "arena_opponent": "agent-opponent",
                }
            ),
            encoding="utf-8",
        )
        arena_run = _run_bridge(
            module,
            "arena_run",
            ["AgentPubKeyTest111", str(scenario_json), actor_id, "embedded", "", "1", "0", "testnet"],
        )
        assert arena_run["metadata"]["x402"]["x402_status"] == "simulated_settled"
        assert str(arena_run["metadata"]["trace_commitment"]).startswith("sha256:")
        assert arena_run["metadata"]["onchain_intent"]["schema"] == "openlvm.arena.intent.v1"
        assert arena_run["metadata"]["onchain_intent"]["cluster"] == "testnet"
        assert arena_run["metadata"]["onchain_submission"]["submission_status"] == "simulated_confirmed"
        assert (
            arena_run["metadata"]["onchain_intent"]["seed_bundle"]["trace_commitment"]
            == arena_run["metadata"]["trace_commitment"]
        )
        assert str(arena_run["metadata"]["onchain_intent"]["intent_commitment"]).startswith("sha256:")
        intent_payload = _run_bridge(module, "arena_intent", [arena_run["arena_run_id"], actor_id])
        assert intent_payload["arena_run_id"] == arena_run["arena_run_id"]
        assert intent_payload["onchain_intent"]["schema"] == "openlvm.arena.intent.v1"
        submit_payload = _run_bridge(module, "arena_submit_intent", [arena_run["arena_run_id"], actor_id, "0", "devnet"])
        assert submit_payload["arena_run_id"] == arena_run["arena_run_id"]
        assert submit_payload["onchain_submission"]["submission_status"] == "simulated_confirmed"
        assert submit_payload["onchain_submission"]["signature"]
        assert submit_payload["onchain_submission"]["cluster"] == "testnet"
        submit_again = _run_bridge(module, "arena_submit_intent", [arena_run["arena_run_id"], actor_id])
        assert submit_again["already_submitted"] is True
        assert submit_again["onchain_submission"]["signature"] == submit_payload["onchain_submission"]["signature"]

        exec_collection = _run_bridge(
            module,
            "create_collection",
            [workspace["workspace_id"], "Exec Collection", actor_id],
        )
        _run_bridge(
            module,
            "save_scenario",
            [
                exec_collection["collection_id"],
                "pass-cmd",
                "examples/swarm.yaml",
                "pass path",
                actor_id,
                'python -c "print(123)"',
                "12000",
                "",
                "{}",
                "[0]",
            ],
        )
        _run_bridge(
            module,
            "save_scenario",
            [
                exec_collection["collection_id"],
                "fail-cmd",
                "examples/swarm.yaml",
                "fail path",
                actor_id,
                'python -c "import sys; sys.exit(4)"',
                "12000",
                "",
                "{}",
                "[0]",
            ],
        )
        exec_run = _run_bridge(
            module,
            "run_collection",
            [exec_collection["collection_id"], "2", "", "", actor_id],
        )
        assert exec_run["summary"]["failed"] >= 1
        rerun_failed = _run_bridge(
            module,
            "run_collection",
            [
                exec_collection["collection_id"],
                "",
                "",
                "",
                actor_id,
                exec_run["run_id"],
                "failed",
            ],
        )
        assert rerun_failed["scenarios_executed"] == 1
        assert rerun_failed["metadata"]["collection"]["scenario_names"] == ["fail-cmd"]

        strict_scenario_json = tmp_path / "arena-scenario-strict.json"
        strict_scenario_json.write_text(
            json.dumps({"id": "arena-strict", "checks": ["wallet"]}),
            encoding="utf-8",
        )
        os.environ["OPENLVM_SOLANA_BRIDGE_MODE"] = "stub"
        with pytest.raises(ValueError):
            module._arena_run(
                [
                    "AgentPubKeyStrict111",
                    str(strict_scenario_json),
                    actor_id,
                    "embedded",
                    "",
                    "1",
                    "1",
                ]
            )
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_workbench_bridge_rejects_invalid_execution_payload(tmp_path):
    operator_db = tmp_path / "operator.db"
    eval_db = tmp_path / "eval.db"
    env = {
        **os.environ,
        "OPENLVM_OPERATOR_DB": str(operator_db),
        "OPENLVM_EVAL_DB": str(eval_db),
    }
    old_env = dict(os.environ)
    os.environ.update(env)
    module = _load_bridge_module()

    try:
        actor_id = "alice#sess1"
        workspace = _run_bridge(module, "create_workspace", ["Team Test", actor_id])
        collection = _run_bridge(
            module,
            "create_collection",
            [workspace["workspace_id"], "Collection A", actor_id],
        )
        with pytest.raises(ValueError, match="execution_env_json"):
            module._save_scenario(
                [
                    collection["collection_id"],
                    "bad-env",
                    "examples/swarm.yaml",
                    "payload",
                    actor_id,
                    "",
                    "30000",
                    "",
                    "[]",
                    "[0]",
                ]
            )
    finally:
        os.environ.clear()
        os.environ.update(old_env)

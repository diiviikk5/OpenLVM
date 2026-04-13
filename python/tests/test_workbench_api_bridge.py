import json
import os
import importlib.util
from pathlib import Path


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
            ["AgentPubKeyTest111", str(scenario_json), actor_id, "embedded", ""],
        )
        assert arena_run["metadata"]["x402"]["x402_status"] == "simulated_settled"
        assert str(arena_run["metadata"]["trace_commitment"]).startswith("sha256:")
        assert arena_run["metadata"]["onchain_intent"]["schema"] == "openlvm.arena.intent.v1"
        assert (
            arena_run["metadata"]["onchain_intent"]["seed_bundle"]["trace_commitment"]
            == arena_run["metadata"]["trace_commitment"]
        )
        assert str(arena_run["metadata"]["onchain_intent"]["intent_commitment"]).startswith("sha256:")
    finally:
        os.environ.clear()
        os.environ.update(old_env)

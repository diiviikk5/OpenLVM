import importlib.util
import json
from pathlib import Path


def _load_summary_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "ci_gate_summary.py"
    spec = importlib.util.spec_from_file_location("ci_gate_summary_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ci_gate_summary_builds_from_artifact_files(tmp_path):
    module = _load_summary_module()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "doctor.json").write_text(
        json.dumps({"ok": False, "missing": ["zig", "solana cli"], "checks": []}),
        encoding="utf-8",
    )
    (artifacts / "arena-preflight.json").write_text(
        json.dumps(
            {
                "ok": False,
                "checks": [
                    {"name": "endpoint", "status": "missing"},
                    {"name": "resolved mode", "status": "missing"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (artifacts / "arena-readiness.json").write_text(
        json.dumps(
            {
                "can_real_submission": False,
                "reasons": ["AgentKit session mode is not active"],
            }
        ),
        encoding="utf-8",
    )
    (artifacts / "ci-gate.json").write_text(
        json.dumps({"ok": False}),
        encoding="utf-8",
    )

    summary = module._build_summary(artifacts)
    assert "Overall: **fail**" in summary
    assert "Doctor missing checks: `zig, solana cli`" in summary
    assert "Arena readiness: **missing**" in summary
    assert "Readiness reasons: `AgentKit session mode is not active`" in summary
    assert "Preflight missing checks: `endpoint, resolved mode`" in summary


def test_ci_gate_summary_falls_back_to_ci_gate_payload(tmp_path):
    module = _load_summary_module()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "ci-gate.json").write_text(
        json.dumps(
            {
                "ok": True,
                "doctor": {"ok": True, "missing": []},
                "arena_preflight": {
                    "ok": True,
                    "checks": [{"name": "resolved mode", "status": "ok"}],
                },
            }
        ),
        encoding="utf-8",
    )

    summary = module._build_summary(artifacts)
    assert "Overall: **ok**" in summary
    assert "Doctor: **ok**" in summary
    assert "Arena readiness: **missing**" in summary
    assert "Arena preflight: **ok**" in summary


def test_ci_gate_summary_prefers_readiness_bundle_payload(tmp_path):
    module = _load_summary_module()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "readiness-bundle.json").write_text(
        json.dumps(
            {
                "ok": True,
                "doctor": {"ok": True, "missing": []},
                "arena_readiness": {"can_real_submission": True, "reasons": []},
                "arena_preflight": {"ok": True, "checks": []},
                "ci_gate": {"ok": True},
                "action_plan": [
                    {"priority": 1, "title": "Set bridge mode", "command": "export OPENLVM_SOLANA_BRIDGE_MODE=agentkit"}
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = module._build_summary(artifacts)
    assert "Overall: **ok**" in summary
    assert "Doctor: **ok**" in summary
    assert "Arena readiness: **ok**" in summary
    assert "Arena preflight: **ok**" in summary
    assert "Top actions: `export OPENLVM_SOLANA_BRIDGE_MODE=agentkit`" in summary

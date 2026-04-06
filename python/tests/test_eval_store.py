from pathlib import Path

from openlvm.eval_store import EvalStore
from openlvm.models import EvalRun, ScenarioRunResult


def _sample_run(run_id: str) -> EvalRun:
    return EvalRun(
        run_id=run_id,
        suite_name="demo",
        suite_version="1.0",
        config_path=str(Path("examples/swarm.yaml")),
        started_at="2026-04-04T00:00:00+00:00",
        completed_at="2026-04-04T00:00:01+00:00",
        scenarios_requested=2,
        scenarios_executed=2,
        summary={"passed": 2, "warnings": 0, "failed": 0},
    )


def test_store_and_get_latest_run(tmp_path):
    store = EvalStore(tmp_path / "eval_store.db")
    run = _sample_run("run-a")
    store.store_run(run)

    latest = store.get_run("latest")
    assert latest.run_id == "run-a"
    assert latest.suite_name == "demo"


def test_compare_runs_returns_summary_delta(tmp_path):
    store = EvalStore(tmp_path / "eval_store.db")
    baseline = _sample_run("run-a")
    candidate = _sample_run("run-b")
    candidate.summary = {"passed": 1, "warnings": 1, "failed": 0}

    store.store_run(baseline)
    store.store_run(candidate)

    diff = store.compare_runs("run-a", "run-b")
    assert diff.summary_delta["passed"] == -1
    assert diff.summary_delta["warnings"] == 1


def test_compare_runs_includes_scenario_and_trace_diffs(tmp_path):
    store = EvalStore(tmp_path / "eval_store.db")
    baseline = _sample_run("run-a")
    candidate = _sample_run("run-b")
    baseline.results = [
        ScenarioRunResult(
            name="cancel-flow",
            fork_id=1,
            input="Cancel my plan",
            status="passed",
            score=0.95,
            network_delay_ms=0,
            warnings=[],
        )
    ]
    candidate.results = [
        ScenarioRunResult(
            name="cancel-flow",
            fork_id=2,
            input="Cancel my plan",
            status="warning",
            score=0.72,
            network_delay_ms=400,
            warnings=["network delay injected on executor: 400ms"],
        )
    ]
    baseline.metadata = {"traces": [{}], "runtime_backend": "simulated", "chaos_targets": []}
    candidate.metadata = {
        "traces": [{}, {}],
        "runtime_backend": "zig",
        "chaos_targets": ["executor"],
    }
    baseline.summary["warning_events"] = 0
    candidate.summary["warning_events"] = 1

    store.store_run(baseline)
    store.store_run(candidate)

    diff = store.compare_runs("run-a", "run-b")
    assert diff.scenario_diffs[0].name == "cancel-flow"
    assert diff.scenario_diffs[0].candidate_status == "warning"
    assert diff.trace_delta["trace_count_delta"] == 1
    assert diff.trace_delta["runtime_backend_changed"] is True
    assert diff.trace_delta["chaos_targets_added"] == ["executor"]

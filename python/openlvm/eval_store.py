"""SQLite-backed storage for OpenLVM eval runs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from .models import EvalRun, RunDiff, ScenarioDiff


class EvalStore:
    """Persist and query eval runs for local comparison and iteration."""

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            root_dir = Path(__file__).resolve().parents[2]
            db_path = root_dir / ".openlvm" / "eval_store.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    suite_name TEXT NOT NULL,
                    suite_version TEXT NOT NULL,
                    config_path TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    scenarios_requested INTEGER NOT NULL,
                    scenarios_executed INTEGER NOT NULL,
                    chaos_mode TEXT,
                    agent_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runs_started_at
                ON runs(started_at DESC)
                """
            )

    def new_run_id(self) -> str:
        return f"run-{uuid.uuid4().hex[:12]}"

    def store_run(self, run: EvalRun) -> str:
        payload = run.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id, suite_name, suite_version, config_path, started_at,
                    completed_at, scenarios_requested, scenarios_executed,
                    chaos_mode, agent_count, status, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.suite_name,
                    run.suite_version,
                    run.config_path,
                    run.started_at,
                    run.completed_at,
                    run.scenarios_requested,
                    run.scenarios_executed,
                    run.chaos_mode,
                    run.agent_count,
                    run.status,
                    payload,
                ),
            )
        return run.run_id

    def get_run(self, run_id: str = "latest") -> EvalRun:
        with self._connect() as conn:
            if run_id == "latest":
                row = conn.execute(
                    "SELECT payload_json FROM runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT payload_json FROM runs WHERE run_id = ?",
                    (run_id,),
                ).fetchone()

        if row is None:
            raise KeyError(f"Run not found: {run_id}")
        return EvalRun.model_validate_json(row["payload_json"])

    def list_runs(self, limit: int = 10) -> list[EvalRun]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [EvalRun.model_validate_json(row["payload_json"]) for row in rows]

    def compare_runs(self, baseline_run_id: str, candidate_run_id: str) -> RunDiff:
        baseline = self.get_run(baseline_run_id)
        candidate = self.get_run(candidate_run_id)
        baseline_passed = baseline.summary.get("passed", 0)
        candidate_passed = candidate.summary.get("passed", 0)
        baseline_failed = baseline.summary.get("failed", 0)
        candidate_failed = candidate.summary.get("failed", 0)
        baseline_score = self._average_score(baseline)
        candidate_score = self._average_score(candidate)
        scenario_diffs = self._build_scenario_diffs(baseline, candidate)
        return RunDiff(
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            summary_delta={
                "passed": candidate_passed - baseline_passed,
                "failed": candidate_failed - baseline_failed,
                "warnings": candidate.summary.get("warnings", 0)
                - baseline.summary.get("warnings", 0),
            },
            score_delta=round(candidate_score - baseline_score, 4),
            baseline_average_score=round(baseline_score, 4),
            candidate_average_score=round(candidate_score, 4),
            scenario_diffs=scenario_diffs,
            trace_delta=self._build_trace_delta(baseline, candidate),
        )

    def get_trace_summary(self, run_id: str = "latest") -> dict:
        run = self.get_run(run_id)
        return {
            "run_id": run.run_id,
            "suite_name": run.suite_name,
            "runtime_backend": run.metadata.get("runtime_backend", "unknown"),
            "trace_count": len(run.metadata.get("traces", [])),
            "scenario_count": len(run.results),
            "warning_events": run.summary.get("warning_events", 0),
        }

    def query(self, sql: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _average_score(run: EvalRun) -> float:
        if not run.results:
            return 0.0
        return sum(result.score for result in run.results) / len(run.results)

    @staticmethod
    def _build_scenario_diffs(baseline: EvalRun, candidate: EvalRun) -> list[ScenarioDiff]:
        baseline_rollups = EvalStore._scenario_rollups(baseline)
        candidate_rollups = EvalStore._scenario_rollups(candidate)
        scenario_names = sorted(set(baseline_rollups) | set(candidate_rollups))
        diffs: list[ScenarioDiff] = []
        for name in scenario_names:
            base = baseline_rollups.get(name, {})
            cand = candidate_rollups.get(name, {})
            base_score = round(base.get("average_score", 0.0), 4)
            cand_score = round(cand.get("average_score", 0.0), 4)
            diffs.append(
                ScenarioDiff(
                    name=name,
                    baseline_status=base.get("status", "missing"),
                    candidate_status=cand.get("status", "missing"),
                    baseline_score=base_score,
                    candidate_score=cand_score,
                    score_delta=round(cand_score - base_score, 4),
                    baseline_delay_ms=int(base.get("average_delay_ms", 0)),
                    candidate_delay_ms=int(cand.get("average_delay_ms", 0)),
                    warning_delta=int(cand.get("warning_count", 0) - base.get("warning_count", 0)),
                )
            )
        return diffs

    @staticmethod
    def _scenario_rollups(run: EvalRun) -> dict[str, dict]:
        rollups: dict[str, dict] = {}
        for result in run.results:
            bucket = rollups.setdefault(
                result.name,
                {
                    "count": 0,
                    "score_total": 0.0,
                    "delay_total": 0,
                    "warning_count": 0,
                    "status": "passed",
                },
            )
            bucket["count"] += 1
            bucket["score_total"] += result.score
            bucket["delay_total"] += result.network_delay_ms
            bucket["warning_count"] += len(result.warnings)
            if result.status != "passed":
                bucket["status"] = result.status

        for bucket in rollups.values():
            count = max(bucket["count"], 1)
            bucket["average_score"] = bucket["score_total"] / count
            bucket["average_delay_ms"] = round(bucket["delay_total"] / count)
        return rollups

    @staticmethod
    def _build_trace_delta(baseline: EvalRun, candidate: EvalRun) -> dict:
        baseline_traces = baseline.metadata.get("traces", [])
        candidate_traces = candidate.metadata.get("traces", [])
        baseline_targets = set(baseline.metadata.get("chaos_targets", []))
        candidate_targets = set(candidate.metadata.get("chaos_targets", []))
        return {
            "baseline_trace_count": len(baseline_traces),
            "candidate_trace_count": len(candidate_traces),
            "trace_count_delta": len(candidate_traces) - len(baseline_traces),
            "warning_event_delta": candidate.summary.get("warning_events", 0)
            - baseline.summary.get("warning_events", 0),
            "runtime_backend_changed": baseline.metadata.get("runtime_backend")
            != candidate.metadata.get("runtime_backend"),
            "baseline_runtime_backend": baseline.metadata.get("runtime_backend", "unknown"),
            "candidate_runtime_backend": candidate.metadata.get("runtime_backend", "unknown"),
            "chaos_targets_added": sorted(candidate_targets - baseline_targets),
            "chaos_targets_removed": sorted(baseline_targets - candidate_targets),
        }

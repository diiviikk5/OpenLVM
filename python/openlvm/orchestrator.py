"""Execution orchestration for OpenLVM test suites."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import load_config
from .eval_store import EvalStore
from .integrations import DeepEvalAdapter, OpenLLMetryAdapter, PromptfooAdapter
from .models import AgentRunSummary, EvalRun, ScenarioConfig, ScenarioRunResult, TestSuiteConfig
from .operator_store import OperatorStore
from .runtime import BaseRuntime, create_runtime


class TestOrchestrator:
    """Turn a suite config into an executable OpenLVM run and persist the result."""

    __test__ = False

    def __init__(
        self,
        runtime: Optional[BaseRuntime] = None,
        eval_store: Optional[EvalStore] = None,
        deepeval_adapter: Optional[DeepEvalAdapter] = None,
        promptfoo_adapter: Optional[PromptfooAdapter] = None,
        openllmetry_adapter: Optional[OpenLLMetryAdapter] = None,
        operator_store: Optional[OperatorStore] = None,
    ):
        self.runtime = runtime or create_runtime()
        self.eval_store = eval_store or EvalStore()
        self.deepeval_adapter = deepeval_adapter or DeepEvalAdapter()
        self.promptfoo_adapter = promptfoo_adapter or PromptfooAdapter()
        self.openllmetry_adapter = openllmetry_adapter or OpenLLMetryAdapter()
        self.operator_store = operator_store or OperatorStore()

    def run_test_suite(
        self,
        config: TestSuiteConfig | str | Path,
        *,
        scenarios: int = 1,
        chaos_mode: Optional[str] = None,
        config_path: Optional[str | Path] = None,
    ) -> EvalRun:
        if isinstance(config, (str, Path)):
            resolved = Path(config)
            config_path = resolved
            config = load_config(resolved)
        suite_dir = (
            Path(config_path).resolve().parent
            if config_path is not None
            else Path.cwd()
        )

        started_at = self._timestamp()
        run_id = self.eval_store.new_run_id()

        registered_agents = self._register_agents(config)
        agent_lookup = {agent.name: agent.agent_id for agent in registered_agents}
        root_agent_id = registered_agents[0].agent_id

        self._apply_chaos(config, agent_lookup, chaos_mode)
        active_chaos_targets = self._active_chaos_targets(config, agent_lookup, chaos_mode)

        scenario_defs = list(config.scenarios.items())
        fork_ids = self.runtime.fork_many(root_agent_id, scenarios)
        fork_parents = {
            fork_id: self._safe_parent_lookup(fork_id) for fork_id in fork_ids
        }
        results: list[ScenarioRunResult] = []
        warnings_total = 0
        trace_records: list[dict] = []
        promptfoo_outputs: list[str] = []

        for index, fork_id in enumerate(fork_ids):
            scenario_name, scenario = scenario_defs[index % len(scenario_defs)]
            execution = self._execute_scenario(scenario, suite_dir=suite_dir)
            chaos_effects = self._collect_chaos_effects(
                active_chaos_targets,
                fork_id=fork_id,
                fork_parent_id=fork_parents.get(fork_id),
            )
            fork_effect = chaos_effects.get("__fork__", {})
            network_delay_ms = int(fork_effect.get("delay_ms", 0))
            warnings = self._collect_warnings(config, scenario_name, chaos_effects, chaos_mode)
            warnings.extend(execution.get("warnings", []))
            warnings_total += len(warnings)
            score = self._score_result(network_delay_ms, warnings, execution)
            status = self._status_from_result(score, execution)
            agent_output = execution.get("output", "") or self._build_agent_output(
                scenario.input,
                network_delay_ms,
                warnings,
            )
            deepeval_metrics = self._run_deepeval_metrics(config, agent_output)
            trace_record = self.openllmetry_adapter.instrument_fork(fork_id)
            trace_record["chaos_effects"] = chaos_effects
            trace_record["scenario_name"] = scenario_name
            trace_record["execution"] = {
                key: value
                for key, value in execution.items()
                if key in {"command", "cwd", "exit_code", "duration_ms", "timed_out", "success"}
            }
            trace_records.append(trace_record)
            promptfoo_outputs.append(agent_output)
            results.append(
                ScenarioRunResult(
                    name=scenario_name,
                    fork_id=fork_id,
                    fork_parent_id=fork_parents.get(fork_id),
                    input=scenario.input,
                    status=status,
                    score=score,
                    network_delay_ms=network_delay_ms,
                    warnings=warnings,
                    chaos_effects=chaos_effects,
                    metrics={
                        "task_completion": score,
                        "tool_correctness": max(score - 0.05, 0.0),
                        "plan_adherence": max(score - 0.03, 0.0),
                        "execution_exit_code": float(
                            execution["exit_code"]
                            if execution.get("exit_code") is not None
                            else 0
                        ),
                        **deepeval_metrics,
                    },
                    execution=execution,
                )
            )

        passed = sum(1 for result in results if result.status == "passed")
        warning_runs = sum(1 for result in results if result.status == "warning")
        failed_runs = sum(1 for result in results if result.status == "failed")
        promptfoo_summary = self._run_promptfoo(config, promptfoo_outputs)
        run = EvalRun(
            run_id=run_id,
            suite_name=config.name,
            suite_version=config.version,
            config_path=str(Path(config_path).resolve()) if config_path else "<in-memory>",
            started_at=started_at,
            completed_at=self._timestamp(),
            scenarios_requested=scenarios,
            scenarios_executed=len(results),
            chaos_mode=chaos_mode,
            agent_count=len(registered_agents),
            status="completed",
            summary={
                "passed": passed,
                "warnings": warning_runs,
                "failed": failed_runs,
                "warning_events": warnings_total,
            },
            agents=registered_agents,
            results=results,
            metadata={
                "scenario_templates": list(config.scenarios.keys()),
                "chaos_configured": len(config.chaos),
                "promptfoo": promptfoo_summary,
                "tracing_available": self.openllmetry_adapter.available,
                "deepeval_available": self.deepeval_adapter.available,
                "traces": trace_records,
                "runtime_backend": getattr(self.runtime, "backend", "custom"),
                "chaos_targets": list(active_chaos_targets.keys()),
            },
        )
        self.eval_store.store_run(run)
        return run

    def run_collection(
        self,
        collection_id: str,
        *,
        scenarios: Optional[int] = None,
        chaos_mode: Optional[str] = None,
        scenario_names: Optional[list[str]] = None,
    ) -> EvalRun:
        collection_summary = self.operator_store.get_collection_summary(collection_id)
        saved_scenarios = collection_summary["scenarios"]
        if not saved_scenarios:
            raise ValueError(f"Collection has no saved scenarios: {collection_id}")
        if scenario_names:
            wanted = {name.strip() for name in scenario_names if str(name).strip()}
            filtered = [entry for entry in saved_scenarios if entry["name"] in wanted]
            if not filtered:
                raise ValueError("No saved scenarios matched requested scenario_names")
            saved_scenarios = filtered

        config_paths = {entry["config_path"] for entry in saved_scenarios}
        if len(config_paths) != 1:
            raise ValueError(
                "Collection run requires all saved scenarios to share the same config path"
            )

        config_path = Path(next(iter(config_paths)))
        base_config = load_config(config_path)
        config = base_config.model_copy(deep=True)
        config.name = f"{base_config.name}:{collection_summary['collection']['name']}"
        config.scenarios = {
            entry["name"]: ScenarioConfig(
                input=entry["input_text"],
                execution_command=entry.get("execution_command") or None,
                execution_timeout_ms=int(entry.get("execution_timeout_ms") or 30000),
                execution_cwd=entry.get("execution_cwd") or None,
                execution_env=self._safe_json_dict(entry.get("execution_env_json")),
                success_exit_codes=self._safe_json_int_list(
                    entry.get("success_exit_codes_json"),
                    default=[0],
                ),
            )
            for entry in reversed(saved_scenarios)
        }

        run = self.run_test_suite(
            config,
            scenarios=scenarios or len(saved_scenarios),
            chaos_mode=chaos_mode,
            config_path=config_path,
        )
        run.metadata["collection"] = {
            "collection_id": collection_id,
            "workspace_id": collection_summary["workspace"]["workspace_id"],
            "collection_name": collection_summary["collection"]["name"],
            "scenario_ids": [entry["scenario_id"] for entry in saved_scenarios],
            "scenario_names": [entry["name"] for entry in saved_scenarios],
        }
        self.eval_store.store_run(run)
        return run

    def _register_agents(self, config: TestSuiteConfig) -> list[AgentRunSummary]:
        registered: list[AgentRunSummary] = []
        for agent_name, agent in config.agents.items():
            mask = config.to_capability_mask(agent.capabilities)
            agent_id = self.runtime.register_agent(mask)
            registered.append(
                AgentRunSummary(
                    name=agent_name,
                    agent_id=agent_id,
                    capabilities=agent.capabilities,
                )
            )
        return registered

    def _apply_chaos(
        self,
        config: TestSuiteConfig,
        agent_lookup: dict[str, int],
        chaos_mode: Optional[str],
    ) -> None:
        for entry in config.chaos:
            if chaos_mode not in (None, "all", entry.type):
                continue

            agent_id = agent_lookup.get(entry.target)
            if agent_id is None:
                continue

            probability = entry.params.probability or 0.3
            if entry.type == "network_delay":
                self.runtime.chaos_add_network_delay(
                    agent_id,
                    probability,
                    entry.params.delay_ms or 500,
                )
            elif entry.type == "hallucination":
                self.runtime.chaos_add_hallucination(
                    agent_id,
                    probability,
                    entry.params.corruption_rate or 0.1,
                )

    def _active_chaos_targets(
        self,
        config: TestSuiteConfig,
        agent_lookup: dict[str, int],
        chaos_mode: Optional[str],
    ) -> dict[str, dict]:
        targets: dict[str, dict] = {}
        for entry in config.chaos:
            if chaos_mode not in (None, "all", entry.type):
                continue
            agent_id = agent_lookup.get(entry.target)
            if agent_id is None:
                continue
            targets[entry.target] = {
                "agent_id": agent_id,
                "type": entry.type,
                "probability": entry.params.probability or 0.3,
                "params": entry.params.model_dump(),
            }
        return targets

    def _collect_chaos_effects(
        self,
        active_chaos_targets: dict[str, dict],
        *,
        fork_id: int,
        fork_parent_id: int | None,
    ) -> dict[str, dict]:
        effects: dict[str, dict] = {}
        fork_delay_ms = self.runtime.chaos_get_network_delay(int(fork_id))
        effects["__fork__"] = {
            "agent_id": int(fork_id),
            "parent_agent_id": int(fork_parent_id) if fork_parent_id is not None else None,
            "type": "network_delay",
            "delay_ms": fork_delay_ms,
            "applied": fork_delay_ms > 0,
        }
        for target_name, target in active_chaos_targets.items():
            effect: dict[str, object] = {
                "agent_id": target["agent_id"],
                "type": target["type"],
                "probability": target["probability"],
            }
            if target["type"] == "network_delay":
                delay_ms = self.runtime.chaos_get_network_delay(int(target["agent_id"]))
                effect["delay_ms"] = delay_ms
                effect["applied"] = delay_ms > 0
            elif target["type"] == "hallucination":
                effect["corruption_rate"] = target["params"].get("corruption_rate", 0.0)
                effect["applied"] = True
            else:
                effect["applied"] = False
            effects[target_name] = effect
        return effects

    @staticmethod
    def _collect_warnings(
        config: TestSuiteConfig,
        scenario_name: str,
        chaos_effects: dict[str, dict],
        chaos_mode: Optional[str],
    ) -> list[str]:
        warnings: list[str] = []
        fork_effect = chaos_effects.get("__fork__", {})
        if fork_effect.get("delay_ms", 0) > 0:
            warnings.append(f"network delay injected on fork {fork_effect['agent_id']}: {fork_effect['delay_ms']}ms")
        for target_name, effect in chaos_effects.items():
            if target_name == "__fork__":
                continue
            if effect.get("type") == "network_delay" and effect.get("delay_ms", 0) > 0:
                warnings.append(f"network delay injected on {target_name}: {effect['delay_ms']}ms")
            if effect.get("type") == "hallucination" and effect.get("applied"):
                warnings.append(f"hallucination mode enabled on {target_name}; output integrity degraded")
        if scenario_name not in config.scenarios:
            warnings.append("scenario mapping fallback applied")
        return warnings

    @staticmethod
    def _score_result(
        network_delay_ms: int,
        warnings: list[str],
        execution: dict,
    ) -> float:
        score = 0.96
        if network_delay_ms > 0:
            score -= min(network_delay_ms / 5000.0, 0.2)
        score -= len(warnings) * 0.03
        if execution.get("command"):
            score += 0.02 if execution.get("success") else -0.35
            if execution.get("timed_out"):
                score -= 0.1
        return round(max(score, 0.0), 2)

    @staticmethod
    def _status_from_result(score: float, execution: dict) -> str:
        if execution.get("command") and not execution.get("success", False):
            return "failed"
        return "passed" if score >= 0.75 else "warning"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _build_agent_output(user_input: str, network_delay_ms: int, warnings: list[str]) -> str:
        suffix = f" delay={network_delay_ms}ms" if network_delay_ms else ""
        warning_text = f" warnings={','.join(warnings)}" if warnings else ""
        return f"processed input={user_input!r}{suffix}{warning_text}"

    @staticmethod
    def _execute_scenario(scenario: ScenarioConfig, *, suite_dir: Path) -> dict:
        command = (scenario.execution_command or "").strip()
        if not command:
            return {}

        timeout_ms = max(1, int(scenario.execution_timeout_ms or 30_000))
        cwd = (
            (suite_dir / scenario.execution_cwd).resolve()
            if scenario.execution_cwd
            else suite_dir
        )
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in scenario.execution_env.items()})
        expected_codes = set(scenario.success_exit_codes or [0])
        started = time.perf_counter()
        try:
            with tempfile.NamedTemporaryFile(mode="w+b", delete=True) as stdout_file, tempfile.NamedTemporaryFile(
                mode="w+b", delete=True
            ) as stderr_file:
                completed = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(cwd),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    timeout=timeout_ms / 1000.0,
                    check=False,
                )
                stdout_file.flush()
                stderr_file.flush()
                stdout_file.seek(0)
                stderr_file.seek(0)
                stdout = stdout_file.read().decode("utf-8", errors="replace")
                stderr = stderr_file.read().decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return {
                "command": command,
                "cwd": str(cwd),
                "timed_out": True,
                "duration_ms": duration_ms,
                "exit_code": None,
                "success": False,
                "stdout": (exc.stdout or ""),
                "stderr": (exc.stderr or ""),
                "output": (exc.stdout or exc.stderr or ""),
                "warnings": [f"execution timeout after {timeout_ms}ms for scenario command"],
            }

        duration_ms = int((time.perf_counter() - started) * 1000)
        exit_code = int(completed.returncode)
        success = exit_code in expected_codes
        warnings: list[str] = []
        if not success:
            warnings.append(f"scenario command exited with code {exit_code}")
        output = stdout if stdout.strip() else stderr
        if scenario.expected_behavior and scenario.expected_behavior not in output:
            warnings.append(
                f"expected behavior marker not found in output: {scenario.expected_behavior}"
            )
            success = False
        return {
            "command": command,
            "cwd": str(cwd),
            "timed_out": False,
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "output": output,
            "warnings": warnings,
        }

    def _safe_parent_lookup(self, agent_id: int) -> int | None:
        try:
            return self.runtime.get_parent_agent_id(agent_id)
        except Exception:
            return None

    @staticmethod
    def _safe_json_dict(raw: object) -> dict[str, str]:
        if not raw:
            return {}
        try:
            value = json.loads(str(raw))
        except Exception:
            return {}
        if not isinstance(value, dict):
            return {}
        return {str(key): str(val) for key, val in value.items()}

    @staticmethod
    def _safe_json_int_list(raw: object, *, default: list[int]) -> list[int]:
        if not raw:
            return list(default)
        try:
            value = json.loads(str(raw))
        except Exception:
            return list(default)
        if not isinstance(value, list):
            return list(default)
        result: list[int] = []
        for token in value:
            try:
                result.append(int(token))
            except Exception:
                continue
        return result or list(default)

    def _run_deepeval_metrics(self, config: TestSuiteConfig, agent_output: str) -> dict[str, float]:
        metrics = config.metrics.deepeval or []
        if not metrics:
            return {}
        return self._run_coro(self.deepeval_adapter.evaluate(agent_output, metrics))

    def _run_promptfoo(self, config: TestSuiteConfig, outputs: list[str]) -> dict:
        if not config.metrics.promptfoo:
            return {"enabled": False}
        summary = self._run_coro(self.promptfoo_adapter.run_eval("<generated>", outputs))
        summary["enabled"] = True
        return summary

    @staticmethod
    def _run_coro(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

"""OpenLVM CLI powered by Typer and Rich."""

import json
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .arena import build_onchain_intent, build_trace_commitment
from .eval_store import EvalStore
from .integrations import DeepEvalAdapter, OpenLLMetryAdapter, PromptfooAdapter, SolanaAgentKitAdapter
from .mcp_server import serve as serve_mcp
from .operator_store import OperatorStore
from .orchestrator import TestOrchestrator
from .runtime import OpenLVMError, OpenLVMRuntime, create_runtime
from .solana_hub import integration_readiness, load_solana_integrations

app = typer.Typer(help="OpenLVM - Performance-first Agent-Native VM Runtime")
console = Console()
DEFAULT_EXAMPLE_CONFIG = Path(__file__).resolve().parents[2] / "examples" / "swarm.yaml"


def _agentkit_ping(endpoint: str, api_key: str, timeout_ms: int = 5000) -> tuple[bool, str]:
    payload = {
        "command": "health",
        "payload": {"source": "openlvm.arena-preflight"},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    timeout_s = max(timeout_ms, 1) / 1000.0
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            status = int(getattr(response, "status", 200) or 200)
            body = response.read().decode("utf-8", errors="replace").strip()
            if 200 <= status < 300:
                return True, f"http {status}" if not body else f"http {status} ({body[:120]})"
            return False, f"http {status}"
    except urllib.error.HTTPError as exc:
        return False, f"http {exc.code}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"network error: {reason}"
    except Exception as exc:  # pragma: no cover - defensive path
        return False, f"error: {exc}"


def _write_json_output_file(output_file: Path, payload: dict) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _doctor_payload() -> dict:
    runtime = create_runtime()
    zig_installed = shutil.which("zig") is not None
    solana_installed = shutil.which("solana") is not None
    runtime_mode = os.getenv("OPENLVM_RUNTIME") or "auto"
    shared_lib = OpenLVMRuntime._default_library_path()
    adapter = SolanaAgentKitAdapter()
    bridge_mode_env = os.getenv("OPENLVM_SOLANA_BRIDGE_MODE", "").strip() or "auto"
    agentkit_key = os.getenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "").strip()
    agentkit_endpoint = os.getenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "").strip()

    checks = [
        {"name": "runtime backend", "status": "ok", "detail": runtime.backend},
        {"name": "runtime mode", "status": "ok", "detail": runtime_mode},
        {
            "name": "zig",
            "status": "ok" if zig_installed else "missing",
            "detail": "installed" if zig_installed else "not on PATH",
        },
        {
            "name": "solana cli",
            "status": "ok" if solana_installed else "missing",
            "detail": "installed" if solana_installed else "run: curl -fsSL https://www.solana.new/setup.sh | bash",
        },
        {
            "name": "shared library",
            "status": "ok" if shared_lib.exists() else "missing",
            "detail": str(shared_lib),
        },
        {
            "name": "solana bridge mode",
            "status": "ok",
            "detail": f"resolved={adapter.bridge_mode} env={bridge_mode_env}",
        },
        {
            "name": "agentkit api key",
            "status": "ok" if agentkit_key else "missing",
            "detail": "configured" if agentkit_key else "not set",
        },
        {
            "name": "agentkit endpoint",
            "status": "ok" if agentkit_endpoint else "missing",
            "detail": agentkit_endpoint if agentkit_endpoint else "not set",
        },
        {
            "name": "real submission readiness",
            "status": "ok" if SolanaAgentKitAdapter.is_real_submission_mode(adapter.bridge_mode) else "missing",
            "detail": "agentkit-session ready"
            if SolanaAgentKitAdapter.is_real_submission_mode(adapter.bridge_mode)
            else "requires OPENLVM_SOLANA_BRIDGE_MODE=agentkit + key + endpoint",
        },
        {
            "name": "promptfoo adapter",
            "status": "ok",
            "detail": "available" if PromptfooAdapter().available else "npx not found",
        },
        {
            "name": "deepeval adapter",
            "status": "ok",
            "detail": "available" if DeepEvalAdapter().available else "fallback mode",
        },
        {
            "name": "openllmetry adapter",
            "status": "ok",
            "detail": "available" if OpenLLMetryAdapter().available else "fallback mode",
        },
    ]
    missing = [row["name"] for row in checks if row["status"] != "ok"]
    return {
        "ok": len(missing) == 0,
        "backend": runtime.backend,
        "checks": checks,
        "missing": missing,
    }


def _arena_preflight_payload(*, ping: bool, timeout_ms: int, fail_on_ping_warning: bool) -> dict:
    adapter = SolanaAgentKitAdapter()
    bridge_mode_env = os.getenv("OPENLVM_SOLANA_BRIDGE_MODE", "").strip()
    agentkit_key = os.getenv("OPENLVM_SOLANA_AGENTKIT_API_KEY", "").strip()
    agentkit_endpoint = os.getenv("OPENLVM_SOLANA_AGENTKIT_ENDPOINT", "").strip()
    real_ready = SolanaAgentKitAdapter.is_real_submission_mode(adapter.bridge_mode)

    checks = [
        {
            "name": "bridge mode env",
            "status": "ok" if bridge_mode_env == "agentkit" else "missing",
            "detail": bridge_mode_env or "not set",
        },
        {
            "name": "api key",
            "status": "ok" if agentkit_key else "missing",
            "detail": "configured" if agentkit_key else "not set",
        },
        {
            "name": "endpoint",
            "status": "ok" if agentkit_endpoint else "missing",
            "detail": agentkit_endpoint or "not set",
        },
        {
            "name": "resolved mode",
            "status": "ok" if real_ready else "missing",
            "detail": adapter.bridge_mode,
        },
    ]

    ping_ok = True
    ping_detail = ""
    if ping:
        if not agentkit_endpoint or not agentkit_key:
            ping_ok = False
            ping_detail = "requires endpoint + api key"
            checks.append({"name": "live ping", "status": "missing", "detail": ping_detail})
        else:
            ok, detail = _agentkit_ping(agentkit_endpoint, agentkit_key, timeout_ms=timeout_ms)
            ping_ok = ok
            ping_detail = detail
            checks.append({"name": "live ping", "status": "ok" if ok else "missing", "detail": detail})

    ping_blocking_failure = ping and not ping_ok and fail_on_ping_warning
    overall_ok = real_ready and not ping_blocking_failure
    return {
        "ok": overall_ok,
        "real_submission_ready": real_ready,
        "bridge_mode": adapter.bridge_mode,
        "bridge_mode_env": bridge_mode_env or "",
        "ping_requested": ping,
        "ping_ok": ping_ok if ping else None,
        "ping_detail": ping_detail if ping else "",
        "ping_warning_enforced": fail_on_ping_warning,
        "checks": checks,
    }


def _arena_readiness_payload() -> dict:
    adapter = SolanaAgentKitAdapter()
    readiness = adapter.readiness()
    readiness["cluster"] = os.getenv("OPENLVM_SOLANA_CLUSTER", "devnet")
    return readiness


def _build_action_plan(doctor: dict, readiness: dict, preflight: dict) -> list[dict]:
    plan: list[dict] = []

    def add_action(action_id: str, priority: int, title: str, command: str) -> None:
        if not command.strip():
            return
        if any(item["id"] == action_id for item in plan):
            return
        plan.append(
            {
                "id": action_id,
                "priority": int(priority),
                "title": title,
                "command": command.strip(),
            }
        )

    doctor_actions = {
        "zig": ("install-zig", 1, "Install Zig toolchain", "zig version"),
        "solana cli": ("install-solana-cli", 1, "Install Solana CLI", "solana --version"),
        "agentkit api key": (
            "set-agentkit-api-key",
            1,
            "Set AgentKit API key",
            "export OPENLVM_SOLANA_AGENTKIT_API_KEY=...",
        ),
        "agentkit endpoint": (
            "set-agentkit-endpoint",
            1,
            "Set AgentKit endpoint",
            "export OPENLVM_SOLANA_AGENTKIT_ENDPOINT=https://...",
        ),
        "real submission readiness": (
            "enable-agentkit-mode",
            1,
            "Enable AgentKit session mode",
            "export OPENLVM_SOLANA_BRIDGE_MODE=agentkit",
        ),
    }
    for missing in doctor.get("missing", []) or []:
        key = str(missing).strip().lower()
        if key in doctor_actions:
            action_id, priority, title, command = doctor_actions[key]
            add_action(action_id, priority, title, command)

    for issue in readiness.get("issues", []) or []:
        if not isinstance(issue, dict):
            continue
        issue_id = str(issue.get("id", "")).strip()
        command = str(issue.get("command", "")).strip()
        message = str(issue.get("message", "")).strip() or issue_id
        severity = str(issue.get("severity", "warning")).strip().lower()
        priority = 1 if severity == "critical" else 2 if severity == "warning" else 3
        add_action(f"readiness:{issue_id}" if issue_id else f"readiness:{message}", priority, message, command)

    for check in preflight.get("checks", []) or []:
        if not isinstance(check, dict):
            continue
        if str(check.get("status", "ok")).strip().lower() == "ok":
            continue
        name = str(check.get("name", "")).strip().lower()
        if name == "bridge mode env":
            add_action("preflight:bridge-mode-env", 1, "Set bridge mode to agentkit", "export OPENLVM_SOLANA_BRIDGE_MODE=agentkit")
        elif name == "api key":
            add_action("preflight:api-key", 1, "Configure AgentKit API key", "export OPENLVM_SOLANA_AGENTKIT_API_KEY=...")
        elif name == "endpoint":
            add_action(
                "preflight:endpoint",
                1,
                "Configure AgentKit endpoint",
                "export OPENLVM_SOLANA_AGENTKIT_ENDPOINT=https://...",
            )
        elif name == "live ping":
            add_action(
                "preflight:live-ping",
                2,
                "Validate AgentKit endpoint health",
                "python -m openlvm.cli arena-preflight --ping --json",
            )

    plan.sort(key=lambda item: (int(item.get("priority", 99)), str(item.get("title", ""))))
    return plan


def _readiness_bundle_payload(*, ping: bool, timeout_ms: int, fail_on_ping_warning: bool) -> dict:
    doctor_payload = _doctor_payload()
    arena_readiness_payload = _arena_readiness_payload()
    arena_preflight_payload = _arena_preflight_payload(
        ping=ping,
        timeout_ms=timeout_ms,
        fail_on_ping_warning=fail_on_ping_warning,
    )
    ci_gate_ok = bool(doctor_payload.get("ok")) and bool(arena_preflight_payload.get("ok"))
    ci_gate_payload = {
        "ok": ci_gate_ok,
        "doctor": doctor_payload,
        "arena_preflight": arena_preflight_payload,
        "summary": (
            f"ci-gate: {'ok' if ci_gate_ok else 'fail'} "
            f"| doctor={'ok' if doctor_payload.get('ok') else 'missing'} "
            f"| arena_preflight={'ok' if arena_preflight_payload.get('ok') else 'missing'}"
        ),
    }
    action_plan = _build_action_plan(doctor_payload, arena_readiness_payload, arena_preflight_payload)
    bundle_ok = bool(arena_readiness_payload.get("can_real_submission")) and ci_gate_ok
    return {
        "ok": bundle_ok,
        "doctor": doctor_payload,
        "arena_readiness": arena_readiness_payload,
        "arena_preflight": arena_preflight_payload,
        "ci_gate": ci_gate_payload,
        "action_plan": action_plan,
    }


def _print_run_diff(diff) -> None:
    console.print(
        f"[bold cyan]Comparison[/bold cyan] {diff.baseline_run_id} -> {diff.candidate_run_id}\n"
        f"Passed delta: {diff.summary_delta.get('passed', 0)}  "
        f"Warnings delta: {diff.summary_delta.get('warnings', 0)}  "
        f"Failed delta: {diff.summary_delta.get('failed', 0)}  "
        f"Score delta: {diff.score_delta:+.2f}"
    )
    console.print(
        f"Average score: {diff.baseline_average_score:.2f} -> {diff.candidate_average_score:.2f}"
    )

    if diff.scenario_diffs:
        table = Table(title="Scenario Diffs")
        table.add_column("Scenario", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Score", justify="right", style="magenta")
        table.add_column("Delay", justify="right", style="yellow")
        table.add_column("Warn Δ", justify="right", style="red")
        for scenario in diff.scenario_diffs[:12]:
            table.add_row(
                scenario.name,
                f"{scenario.baseline_status} -> {scenario.candidate_status}",
                f"{scenario.baseline_score:.2f} -> {scenario.candidate_score:.2f}",
                f"{scenario.baseline_delay_ms}ms -> {scenario.candidate_delay_ms}ms",
                f"{scenario.warning_delta:+d}",
            )
        console.print(table)
        if len(diff.scenario_diffs) > 12:
            console.print(f"... and [cyan]{len(diff.scenario_diffs) - 12}[/cyan] more scenario diffs.")

    trace_delta = diff.trace_delta or {}
    console.print(
        f"Trace delta: {trace_delta.get('baseline_trace_count', 0)} -> "
        f"{trace_delta.get('candidate_trace_count', 0)}  "
        f"Warning events delta: {trace_delta.get('warning_event_delta', 0):+d}"
    )
    if trace_delta.get("runtime_backend_changed"):
        console.print(
            f"Runtime backend changed: {trace_delta.get('baseline_runtime_backend')} -> "
            f"{trace_delta.get('candidate_runtime_backend')}"
        )
    if trace_delta.get("chaos_targets_added") or trace_delta.get("chaos_targets_removed"):
        console.print(
            f"Chaos targets added: {', '.join(trace_delta.get('chaos_targets_added', [])) or 'none'}"
        )
        console.print(
            f"Chaos targets removed: {', '.join(trace_delta.get('chaos_targets_removed', [])) or 'none'}"
        )


@app.command()
def info():
    """Print system information and Zig runtime status."""
    console.print("[bold cyan]OpenLVM Runtime Info[/bold cyan]")
    try:
        runtime = create_runtime()
        console.print(f"Version: [green]{runtime.version()}[/green]")
        console.print(f"Backend: [cyan]{runtime.backend}[/cyan]")
        console.print(f"Active Agents: [yellow]{runtime.get_active_agent_count()}[/yellow]")
    except Exception as exc:
        console.print(f"[bold red]Failed to load runtime:[/bold red] {exc}")


@app.command()
def doctor(
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON output"),
    output_file: Optional[Path] = typer.Option(None, "--output-file", help="Write JSON payload to file"),
):
    """Inspect local OpenLVM readiness."""
    payload = _doctor_payload()
    if output_file:
        _write_json_output_file(output_file, payload)
    checks = payload["checks"]
    if json_output:
        console.print_json(json.dumps(payload))
        return

    table = Table(title="OpenLVM Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Detail", style="magenta")
    for row in checks:
        table.add_row(str(row["name"]), str(row["status"]), str(row["detail"]))
    console.print(table)


@app.command("arena-preflight")
def arena_preflight(
    ping: bool = typer.Option(False, "--ping", help="Perform a live ping to AgentKit endpoint"),
    timeout_ms: int = typer.Option(5000, "--timeout-ms", help="Timeout for --ping request"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON output"),
    output_file: Optional[Path] = typer.Option(None, "--output-file", help="Write JSON payload to file"),
    fail_on_ping_warning: bool = typer.Option(
        True,
        "--fail-on-ping-warning/--allow-ping-warning",
        help="When --ping is used, fail if ping is not successful",
    ),
):
    """Check readiness for strict real Arena submission mode."""
    payload = _arena_preflight_payload(
        ping=ping,
        timeout_ms=timeout_ms,
        fail_on_ping_warning=fail_on_ping_warning,
    )
    if output_file:
        _write_json_output_file(output_file, payload)
    checks = payload["checks"]
    overall_ok = bool(payload["ok"])
    if json_output:
        console.print_json(json.dumps(payload))
    else:
        table = Table(title="Arena Preflight")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Detail", style="magenta")
        for row in checks:
            table.add_row(str(row["name"]), str(row["status"]), str(row["detail"]))
        console.print(table)
    if not overall_ok:
        raise typer.Exit(code=1)


@app.command("arena-readiness")
def arena_readiness(
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON output"),
    output_file: Optional[Path] = typer.Option(None, "--output-file", help="Write JSON payload to file"),
):
    """Show Solana Arena real-submission readiness details."""
    payload = _arena_readiness_payload()
    if output_file:
        _write_json_output_file(output_file, payload)
    if json_output:
        console.print_json(json.dumps(payload))
        return
    table = Table(title="Arena Readiness")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("adapter mode", str(payload.get("adapter_mode", "")))
    table.add_row("real submission ready", "yes" if payload.get("can_real_submission") else "no")
    table.add_row("cluster", str(payload.get("cluster", "")))
    table.add_row("bridge script", str(payload.get("bridge_script", "")))
    table.add_row("readiness score", str(payload.get("readiness_score", "")))
    reasons = payload.get("reasons", [])
    table.add_row("reasons", ", ".join(reasons) if isinstance(reasons, list) and reasons else "none")
    next_actions = payload.get("next_actions", [])
    table.add_row("next actions", ", ".join(next_actions) if isinstance(next_actions, list) and next_actions else "none")
    console.print(table)


@app.command("ci-gate")
def ci_gate(
    ping: bool = typer.Option(True, "--ping/--no-ping", help="Include live AgentKit ping in preflight"),
    timeout_ms: int = typer.Option(5000, "--timeout-ms", help="Timeout for ping request"),
    fail_on_ping_warning: bool = typer.Option(
        True,
        "--fail-on-ping-warning/--allow-ping-warning",
        help="When ping is enabled, fail gate if ping is not successful",
    ),
    json_output: bool = typer.Option(True, "--json/--text", help="Print machine-readable JSON output"),
    summary: bool = typer.Option(False, "--summary", help="Print compact single-line status output"),
    output_file: Optional[Path] = typer.Option(None, "--output-file", help="Write JSON payload to file"),
):
    """Run consolidated CI readiness gate (doctor + arena preflight)."""
    doctor_payload = _doctor_payload()
    preflight_payload = _arena_preflight_payload(
        ping=ping,
        timeout_ms=timeout_ms,
        fail_on_ping_warning=fail_on_ping_warning,
    )
    overall_ok = bool(doctor_payload.get("ok")) and bool(preflight_payload.get("ok"))
    payload = {
        "ok": overall_ok,
        "doctor": doctor_payload,
        "arena_preflight": preflight_payload,
    }
    summary_line = (
        f"ci-gate: {'ok' if overall_ok else 'fail'} "
        f"| doctor={'ok' if doctor_payload.get('ok') else 'missing'} "
        f"| arena_preflight={'ok' if preflight_payload.get('ok') else 'missing'}"
    )
    if preflight_payload.get("ping_requested"):
        ping_ok = preflight_payload.get("ping_ok")
        ping_state = "ok" if ping_ok else "missing"
        summary_line = f"{summary_line} | ping={ping_state}"
    payload["summary"] = summary_line
    if output_file:
        _write_json_output_file(output_file, payload)
    if json_output:
        console.print_json(json.dumps(payload))
    else:
        if summary:
            console.print(summary_line)
            if not overall_ok:
                raise typer.Exit(code=1)
            return
        table = Table(title="OpenLVM CI Gate")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_row("doctor", "ok" if doctor_payload.get("ok") else "missing")
        table.add_row("arena_preflight", "ok" if preflight_payload.get("ok") else "missing")
        table.add_row("overall", "ok" if overall_ok else "missing")
        console.print(table)
    if not overall_ok:
        raise typer.Exit(code=1)


@app.command("readiness-bundle")
def readiness_bundle(
    artifacts_dir: Path = typer.Option(Path("artifacts"), "--artifacts-dir", help="Output directory for JSON artifacts"),
    ping: bool = typer.Option(True, "--ping/--no-ping", help="Include live AgentKit ping in preflight"),
    timeout_ms: int = typer.Option(5000, "--timeout-ms", help="Timeout for ping request"),
    fail_on_ping_warning: bool = typer.Option(
        True,
        "--fail-on-ping-warning/--allow-ping-warning",
        help="When ping is enabled, fail bundle if ping is not successful",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON output"),
):
    """Run all readiness checks and write bundled JSON artifacts for local/CI use."""
    payload = _readiness_bundle_payload(
        ping=ping,
        timeout_ms=timeout_ms,
        fail_on_ping_warning=fail_on_ping_warning,
    )
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    _write_json_output_file(artifacts_dir / "doctor.json", payload["doctor"])
    _write_json_output_file(artifacts_dir / "arena-readiness.json", payload["arena_readiness"])
    _write_json_output_file(artifacts_dir / "arena-preflight.json", payload["arena_preflight"])
    _write_json_output_file(artifacts_dir / "ci-gate.json", payload["ci_gate"])
    _write_json_output_file(artifacts_dir / "readiness-bundle.json", payload)
    if json_output:
        console.print_json(json.dumps(payload))
    else:
        table = Table(title="Readiness Bundle")
        table.add_column("Artifact", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Path", style="magenta")
        table.add_row("doctor", "ok" if payload["doctor"].get("ok") else "missing", str(artifacts_dir / "doctor.json"))
        table.add_row(
            "arena_readiness",
            "ok" if payload["arena_readiness"].get("can_real_submission") else "missing",
            str(artifacts_dir / "arena-readiness.json"),
        )
        table.add_row(
            "arena_preflight",
            "ok" if payload["arena_preflight"].get("ok") else "missing",
            str(artifacts_dir / "arena-preflight.json"),
        )
        table.add_row("ci_gate", "ok" if payload["ci_gate"].get("ok") else "missing", str(artifacts_dir / "ci-gate.json"))
        table.add_row("bundle", "ok" if payload.get("ok") else "missing", str(artifacts_dir / "readiness-bundle.json"))
        console.print(table)
        action_plan = payload.get("action_plan", [])
        if action_plan:
            actions_table = Table(title="Readiness Action Plan")
            actions_table.add_column("Priority", justify="right", style="yellow")
            actions_table.add_column("Action", style="cyan")
            actions_table.add_column("Command", style="magenta")
            for action in action_plan[:10]:
                actions_table.add_row(
                    str(action.get("priority", "")),
                    str(action.get("title", "")),
                    str(action.get("command", "")),
                )
            console.print(actions_table)
    if not payload.get("ok"):
        raise typer.Exit(code=1)


@app.command("readiness-plan")
def readiness_plan(
    ping: bool = typer.Option(True, "--ping/--no-ping", help="Include live AgentKit ping in preflight"),
    timeout_ms: int = typer.Option(5000, "--timeout-ms", help="Timeout for ping request"),
    fail_on_ping_warning: bool = typer.Option(
        True,
        "--fail-on-ping-warning/--allow-ping-warning",
        help="When ping is enabled, fail readiness plan if ping is not successful",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON output"),
    output_file: Optional[Path] = typer.Option(None, "--output-file", help="Write JSON payload to file"),
):
    """Show prioritized commands to move the project toward full readiness."""
    bundle = _readiness_bundle_payload(
        ping=ping,
        timeout_ms=timeout_ms,
        fail_on_ping_warning=fail_on_ping_warning,
    )
    payload = {
        "ok": bundle.get("ok", False),
        "action_plan": bundle.get("action_plan", []),
    }
    if output_file:
        _write_json_output_file(output_file, payload)
    if json_output:
        console.print_json(json.dumps(payload))
    else:
        table = Table(title="Readiness Plan")
        table.add_column("Priority", justify="right", style="yellow")
        table.add_column("Action", style="cyan")
        table.add_column("Command", style="magenta")
        for action in payload["action_plan"]:
            table.add_row(
                str(action.get("priority", "")),
                str(action.get("title", "")),
                str(action.get("command", "")),
            )
        if not payload["action_plan"]:
            table.add_row("-", "No actions required", "none")
        console.print(table)
    if not payload.get("ok"):
        raise typer.Exit(code=1)


@app.command()
def bench(
    count: int = typer.Option(1000, "--count", "-n", help="Number of forks to create"),
):
    """Benchmark the active runtime backend."""
    runtime = create_runtime()
    parent = runtime.register_agent(0)
    started = time.perf_counter()
    children = runtime.fork_many(parent, count)
    elapsed_s = max(time.perf_counter() - started, 1e-9)

    console.print(
        f"[bold cyan]OpenLVM Benchmark[/bold cyan]\n"
        f"Backend: {runtime.backend}\n"
        f"Forks: {len(children)}\n"
        f"Elapsed: {elapsed_s * 1000:.2f}ms\n"
        f"Rate: {len(children) / elapsed_s:.0f} forks/sec"
    )


@app.command()
def test(
    config_path: Path = typer.Argument(..., help="Path to swarm.yaml test config"),
    scenarios: int = typer.Option(1, "--scenarios", "-n", help="Number of parallel universes to fork"),
    chaos_mode: str = typer.Option(None, "--chaos", "-c", help="Specific chaos mode to apply, or 'all'"),
):
    """Run an OpenLVM test suite on an agent graph."""
    try:
        run = TestOrchestrator().run_test_suite(
            config_path,
            scenarios=scenarios,
            chaos_mode=chaos_mode,
        )

        console.print(
            f"[bold green]Run complete:[/bold green] {run.suite_name} {run.suite_version} ({run.run_id})"
        )
        console.print(
            f"Agents: [cyan]{run.agent_count}[/cyan]  "
            f"Scenarios: [cyan]{run.scenarios_executed}[/cyan]  "
            f"Chaos: [yellow]{run.chaos_mode or 'off'}[/yellow]"
        )

        table = Table(title="Simulation Results")
        table.add_column("Scenario", style="cyan")
        table.add_column("Fork ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Result", style="green")
        table.add_column("Network Delay", justify="right", style="yellow")
        table.add_column("Score", justify="right", style="magenta")

        for result in run.results[:10]:
            table.add_row(
                result.name,
                str(result.fork_id),
                result.status,
                f"{result.network_delay_ms}ms" if result.network_delay_ms > 0 else "0ms",
                f"{result.score:.2f}",
            )

        console.print()
        console.print(table)
        if len(run.results) > 10:
            console.print(f"... and [cyan]{len(run.results) - 10}[/cyan] more results hidden.")

        console.print("\n[bold]Run summary:[/bold]")
        console.print(
            f"  Total passed: [green]{run.summary['passed']}[/green] \n"
            f"  Warnings: [yellow]{run.summary['warnings']}[/yellow] \n"
            f"  Failures: [red]{run.summary['failed']}[/red]"
        )

    except FileNotFoundError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except OpenLVMError as exc:
        console.print(f"[bold red]Zig Runtime error ({exc.code}):[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def init(
    output: Path = typer.Argument(Path("openlvm.yaml"), help="Where to write the starter config"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file"),
):
    """Create a starter OpenLVM suite config."""
    if output.exists() and not force:
        console.print(f"[bold red]Refusing to overwrite:[/bold red] {output}")
        raise typer.Exit(code=1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(DEFAULT_EXAMPLE_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[green]Wrote starter config:[/green] {output}")


@app.command()
def results(limit: int = typer.Option(10, "--limit", "-n", help="Number of recent runs to display")):
    """List recent stored runs from the local EvalStore."""
    runs = EvalStore().list_runs(limit=limit)
    if not runs:
        console.print("[yellow]No eval runs stored yet.[/yellow]")
        raise typer.Exit(code=0)

    table = Table(title="Recent OpenLVM Runs")
    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("Suite", style="green")
    table.add_column("Scenarios", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Started", style="magenta")

    for run in runs:
        table.add_row(
            run.run_id,
            run.suite_name,
            str(run.scenarios_executed),
            str(run.summary.get("passed", 0)),
            str(run.summary.get("warnings", 0)),
            run.started_at,
        )

    console.print(table)


@app.command("show-run")
def show_run(
    run_id: str = typer.Argument("latest", help="Run id to inspect"),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON"),
):
    """Show one stored run in detail."""
    run = EvalStore().get_run(run_id)
    if json_output:
        console.print_json(json.dumps(run.model_dump()))
        return

    console.print(
        f"[bold cyan]{run.run_id}[/bold cyan]  {run.suite_name} {run.suite_version}\n"
        f"Status: {run.status}  Scenarios: {run.scenarios_executed}/{run.scenarios_requested}  "
        f"Chaos: {run.chaos_mode or 'off'}"
    )
    table = Table(title="Scenario Results")
    table.add_column("Scenario", style="cyan")
    table.add_column("Fork", justify="right")
    table.add_column("Status", style="green")
    table.add_column("Score", justify="right", style="magenta")
    for result in run.results[:20]:
        table.add_row(result.name, str(result.fork_id), result.status, f"{result.score:.2f}")
    console.print(table)

    if run.metadata.get("traces"):
        trace_summary = EvalStore().get_trace_summary(run.run_id)
        console.print(
            f"Trace summary: traces={trace_summary['trace_count']} "
            f"runtime={trace_summary['runtime_backend']} warnings={trace_summary['warning_events']}"
        )


@app.command("compare")
def compare_runs(
    run_a: str = typer.Argument(..., help="Baseline run id"),
    run_b: str = typer.Argument(..., help="Candidate run id"),
):
    """Compare two stored runs."""
    diff = EvalStore().compare_runs(run_a, run_b)
    _print_run_diff(diff)


@app.command("trace-summary")
def trace_summary(run_id: str = typer.Argument("latest", help="Run id to inspect")):
    """Show trace summary for a run."""
    summary = EvalStore().get_trace_summary(run_id)
    console.print(
        f"[bold cyan]Trace Summary[/bold cyan] {summary['run_id']}\n"
        f"Suite: {summary['suite_name']}\n"
        f"Runtime: {summary['runtime_backend']}\n"
        f"Traces: {summary['trace_count']}\n"
        f"Scenarios: {summary['scenario_count']}\n"
        f"Warning events: {summary['warning_events']}"
    )


@app.command("workspace-create")
def workspace_create(
    name: str = typer.Argument(..., help="Workspace name"),
    description: str = typer.Option("", "--description", "-d", help="Workspace description"),
):
    """Create a workspace for agent testing collections."""
    workspace = OperatorStore().create_workspace(name, description)
    console.print(f"[green]Workspace created:[/green] {workspace.workspace_id} {workspace.name}")


@app.command("workspace-list")
def workspace_list():
    """List workspaces."""
    rows = OperatorStore().list_workspaces()
    table = Table(title="OpenLVM Workspaces")
    table.add_column("Workspace ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description")
    for row in rows:
        table.add_row(row.workspace_id, row.name, row.description)
    console.print(table)


@app.command("collection-create")
def collection_create(
    workspace_id: str = typer.Argument(..., help="Workspace id"),
    name: str = typer.Argument(..., help="Collection name"),
    description: str = typer.Option("", "--description", "-d", help="Collection description"),
):
    """Create a collection inside a workspace."""
    collection = OperatorStore().create_collection(workspace_id, name, description)
    console.print(f"[green]Collection created:[/green] {collection.collection_id} {collection.name}")


@app.command("collection-list")
def collection_list(workspace_id: str = typer.Option(None, "--workspace", help="Filter by workspace id")):
    """List collections."""
    rows = OperatorStore().list_collections(workspace_id)
    table = Table(title="OpenLVM Collections")
    table.add_column("Collection ID", style="cyan")
    table.add_column("Workspace ID", style="yellow")
    table.add_column("Name", style="green")
    for row in rows:
        table.add_row(row.collection_id, row.workspace_id, row.name)
    console.print(table)


@app.command("collection-inspect")
def collection_inspect(collection_id: str = typer.Argument(..., help="Collection id")):
    """Inspect one collection with saved scenarios and baselines."""
    summary = OperatorStore().get_collection_summary(collection_id)
    collection = summary["collection"]
    console.print(
        f"[bold cyan]{collection['collection_id']}[/bold cyan]  {collection['name']}\n"
        f"Workspace: {summary['workspace']['workspace_id']} ({summary['workspace']['name']})\n"
        f"Scenarios: {summary['scenario_count']}  Baselines: {summary['baseline_count']}"
    )

    if summary["scenarios"]:
        scenario_table = Table(title="Collection Scenarios")
        scenario_table.add_column("Scenario ID", style="cyan")
        scenario_table.add_column("Name", style="green")
        scenario_table.add_column("Input")
        for row in summary["scenarios"]:
            scenario_table.add_row(row["scenario_id"], row["name"], row["input_text"])
        console.print(scenario_table)

    if summary["baselines"]:
        baseline_table = Table(title="Collection Baselines")
        baseline_table.add_column("Baseline ID", style="cyan")
        baseline_table.add_column("Run ID", style="yellow")
        baseline_table.add_column("Label", style="green")
        for row in summary["baselines"]:
            baseline_table.add_row(row["baseline_id"], row["run_id"], row["label"])
        console.print(baseline_table)


@app.command("collection-run")
def collection_run(
    collection_id: str = typer.Argument(..., help="Collection id"),
    scenarios: Optional[int] = typer.Option(None, "--scenarios", "-n", help="Number of scenario forks to execute"),
    chaos_mode: str = typer.Option(None, "--chaos", "-c", help="Specific chaos mode to apply, or 'all'"),
):
    """Run a saved collection as a test suite."""
    run = TestOrchestrator().run_collection(
        collection_id,
        scenarios=scenarios,
        chaos_mode=chaos_mode,
    )
    collection_meta = run.metadata.get("collection", {})
    console.print(
        f"[bold green]Collection run complete:[/bold green] "
        f"{collection_meta.get('collection_name', collection_id)} ({run.run_id})"
    )
    console.print(
        f"Workspace: {collection_meta.get('workspace_id', 'unknown')}  "
        f"Scenarios: {run.scenarios_executed}  Chaos: {run.chaos_mode or 'off'}"
    )
    console.print(f"Passed: {run.summary.get('passed', 0)}  Warnings: {run.summary.get('warnings', 0)}")


@app.command("scenario-save")
def scenario_save(
    collection_id: str = typer.Argument(..., help="Collection id"),
    name: str = typer.Argument(..., help="Scenario name"),
    config_path: Path = typer.Argument(..., help="Config path"),
    input_text: str = typer.Argument(..., help="Scenario input text"),
):
    """Save a scenario to a collection."""
    scenario = OperatorStore().save_scenario(collection_id, name, str(config_path), input_text)
    console.print(f"[green]Scenario saved:[/green] {scenario.scenario_id} {scenario.name}")


@app.command("scenario-list")
def scenario_list(collection_id: str = typer.Argument(..., help="Collection id")):
    """List saved scenarios for a collection."""
    rows = OperatorStore().list_saved_scenarios(collection_id)
    table = Table(title="Saved Scenarios")
    table.add_column("Scenario ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Config Path")
    for row in rows:
        table.add_row(row.scenario_id, row.name, row.config_path)
    console.print(table)


@app.command("baseline-save")
def baseline_save(
    collection_id: str = typer.Argument(..., help="Collection id"),
    run_id: str = typer.Argument(..., help="Run id"),
    label: str = typer.Argument(..., help="Baseline label"),
):
    """Save a run as a collection baseline."""
    baseline = OperatorStore().create_baseline(collection_id, run_id, label)
    console.print(f"[green]Baseline saved:[/green] {baseline.baseline_id} {baseline.label}")


@app.command("baseline-list")
def baseline_list(collection_id: str = typer.Argument(..., help="Collection id")):
    """List baselines for a collection."""
    rows = OperatorStore().list_baselines(collection_id)
    table = Table(title="Baselines")
    table.add_column("Baseline ID", style="cyan")
    table.add_column("Run ID", style="yellow")
    table.add_column("Label", style="green")
    for row in rows:
        table.add_row(row.baseline_id, row.run_id, row.label)
    console.print(table)


@app.command("baseline-compare")
def baseline_compare(
    collection_id: str = typer.Argument(..., help="Collection id"),
    run_id: str = typer.Argument(..., help="Candidate run id"),
):
    """Compare the latest baseline in a collection to a run."""
    baselines = OperatorStore().list_baselines(collection_id)
    if not baselines:
        console.print("[bold red]No baselines found for collection.[/bold red]")
        raise typer.Exit(code=1)

    baseline = baselines[0]
    diff = EvalStore().compare_runs(baseline.run_id, run_id)
    console.print(
        f"[bold cyan]Baseline Compare[/bold cyan] {baseline.label}\n"
        f"Baseline run: {baseline.run_id}\n"
        f"Candidate run: {run_id}"
    )
    _print_run_diff(diff)


@app.command("arena-run")
def arena_run(
    agent: str = typer.Option(..., "--agent", help="Solana agent pubkey/address"),
    scenario: Path = typer.Option(..., "--scenario", help="Path to scenario JSON payload"),
    wallet_provider: str = typer.Option("embedded", "--wallet-provider", help="Wallet mode: embedded|private_key|external"),
    private_key: Optional[str] = typer.Option(None, "--private-key", help="Optional private key for local test wallets"),
    cluster: Optional[str] = typer.Option(None, "--cluster", help="Solana cluster override (devnet|testnet|mainnet-beta)"),
    submit_intent: bool = typer.Option(False, "--submit-intent", help="Submit onchain intent immediately after run"),
    require_real_submission: bool = typer.Option(
        False,
        "--require-real-submission",
        help="Fail unless onchain submission runs in AgentKit session mode",
    ),
    actor_id: str = typer.Option("arena-cli", "--actor-id", help="Actor id for audit trail"),
):
    """Run one Solana Arena scenario using the current local simulation engine."""
    if not scenario.exists():
        console.print(f"[bold red]Scenario file not found:[/bold red] {scenario}")
        raise typer.Exit(code=1)

    cluster_name = (cluster or os.getenv("OPENLVM_SOLANA_CLUSTER", "devnet")).strip() or "devnet"
    payload = json.loads(scenario.read_text(encoding="utf-8"))
    scenario_id = str(payload.get("id") or scenario.stem)
    checks = payload.get("checks", [])
    check_count = len(checks) if isinstance(checks, list) else 0
    score = round(min(0.6 + check_count * 0.05, 0.99), 2)
    status = "passed" if score >= 0.75 else "warning"
    entry_fee_usdc = float(payload.get("entry_fee_usdc", 0.05))
    opponent = str(payload.get("arena_opponent", "arena-pool"))

    adapter = SolanaAgentKitAdapter()
    identity = adapter.connect_agent(
        agent_address=agent,
        wallet_provider=wallet_provider,
        private_key=private_key,
    )
    payment = adapter.simulate_x402_transfer(
        from_agent=identity.address,
        to_agent=opponent,
        amount_usdc=entry_fee_usdc,
    )
    trace_commitment = build_trace_commitment(
        {
            "agent": identity.address,
            "scenario_id": scenario_id,
            "score": score,
            "status": status,
            "x402": payment,
            "scenario": payload,
        }
    )
    onchain_intent = build_onchain_intent(
        agent_address=identity.address,
        scenario_id=scenario_id,
        score=score,
        status=status,
        payment=payment,
        trace_commitment=trace_commitment,
        cluster=cluster_name,
    )
    metadata = {
        "wallet_provider": identity.wallet_provider,
        "adapter_mode": identity.metadata.get("adapter_mode", "mvp-local"),
        "x402": payment,
        "trace_commitment": trace_commitment,
        "onchain_intent": onchain_intent,
        "scenario": payload,
    }
    if submit_intent:
        intent_commitment = str(onchain_intent.get("intent_commitment", "")).strip()
        submission_cluster = str(onchain_intent.get("cluster", "devnet") or "devnet")
        if not intent_commitment:
            console.print("[bold red]Intent commitment missing.[/bold red]")
            raise typer.Exit(code=1)
        submission = adapter.submit_onchain_intent(
            intent_commitment=intent_commitment,
            cluster=submission_cluster,
        )
        mode = str(submission.get("metadata", {}).get("adapter_mode", adapter.bridge_mode))
        if require_real_submission and not SolanaAgentKitAdapter.is_real_submission_mode(mode):
            console.print(
                "[bold red]Submission did not use AgentKit session mode while real submission is required.[/bold red]"
            )
            raise typer.Exit(code=1)
        metadata["onchain_submission"] = submission
    record = OperatorStore().create_arena_run(
        identity.address,
        scenario_id,
        score,
        status,
        metadata=metadata,
        actor_id=actor_id,
    )

    console.print(
        f"[bold green]Arena run complete:[/bold green] {record.arena_run_id}\n"
        f"Agent: {record.agent_address}\n"
        f"Scenario: {record.scenario_id}\n"
        f"Score: {record.score:.2f} ({record.status})\n"
        f"x402: {payment.get('x402_status')} {payment.get('amount_usdc')} USDC ({payment.get('tx_ref')})\n"
        f"Trace commitment: {trace_commitment}"
    )
    submission = record.metadata.get("onchain_submission", {})
    if isinstance(submission, dict) and submission.get("signature"):
        console.print(
            f"Onchain submission: {submission.get('submission_status')} {submission.get('signature')}\n"
            f"Explorer: {submission.get('explorer_url')}"
        )


@app.command("arena-runs")
def arena_runs(limit: int = typer.Option(20, "--limit", "-n", help="Number of recent arena runs")):
    """List recent Solana Arena runs."""
    rows = OperatorStore().list_arena_runs(limit=limit)
    table = Table(title="Solana Arena Runs")
    table.add_column("Arena Run ID", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Scenario", style="yellow")
    table.add_column("Score", justify="right", style="magenta")
    table.add_column("Status")
    for row in rows:
        table.add_row(row.arena_run_id, row.agent_address, row.scenario_id, f"{row.score:.2f}", row.status)
    console.print(table)


@app.command("arena-intent")
def arena_intent(
    arena_run_id: str = typer.Argument(..., help="Arena run id"),
    json_output: bool = typer.Option(True, "--json/--text", help="Print JSON (default) or compact text"),
):
    """Show the onchain intent payload for one stored arena run."""
    run = OperatorStore().get_arena_run(arena_run_id)
    intent = run.metadata.get("onchain_intent")
    if not isinstance(intent, dict):
        console.print(f"[bold red]No onchain intent found for run:[/bold red] {arena_run_id}")
        raise typer.Exit(code=1)

    payload = {
        "arena_run_id": run.arena_run_id,
        "agent_address": run.agent_address,
        "scenario_id": run.scenario_id,
        "trace_commitment": run.metadata.get("trace_commitment", ""),
        "onchain_intent": intent,
    }
    if json_output:
        console.print_json(json.dumps(payload))
        return
    console.print(
        f"[bold cyan]{run.arena_run_id}[/bold cyan]\n"
        f"Agent: {run.agent_address}\n"
        f"Scenario: {run.scenario_id}\n"
        f"Trace commitment: {run.metadata.get('trace_commitment', '-')}\n"
        f"Intent commitment: {intent.get('intent_commitment', '-')}"
    )


@app.command("arena-submit")
def arena_submit(
    arena_run_id: str = typer.Argument(..., help="Arena run id"),
    cluster: Optional[str] = typer.Option(None, "--cluster", help="Override cluster for submission"),
    require_real_submission: bool = typer.Option(
        False,
        "--require-real-submission",
        help="Fail unless onchain submission runs in AgentKit session mode",
    ),
    actor_id: str = typer.Option("arena-cli", "--actor-id", help="Actor id for audit trail"),
):
    """Submit stored onchain intent through Solana adapter and persist submission receipt."""
    store = OperatorStore()
    run = store.get_arena_run(arena_run_id)
    intent = run.metadata.get("onchain_intent")
    if not isinstance(intent, dict):
        console.print(f"[bold red]No onchain intent found for run:[/bold red] {arena_run_id}")
        raise typer.Exit(code=1)
    intent_commitment = str(intent.get("intent_commitment", "")).strip()
    cluster_name = (cluster or str(intent.get("cluster", "devnet"))).strip() or "devnet"
    if not intent_commitment:
        console.print("[bold red]Intent commitment missing.[/bold red]")
        raise typer.Exit(code=1)
    existing_submission = run.metadata.get("onchain_submission")
    if isinstance(existing_submission, dict) and existing_submission.get("signature"):
        console.print(
            f"[yellow]Arena intent already submitted:[/yellow] {arena_run_id}\n"
            f"Signature: {existing_submission.get('signature')}\n"
            f"Explorer: {existing_submission.get('explorer_url')}"
        )
        raise typer.Exit(code=0)
    adapter = SolanaAgentKitAdapter()
    submission = adapter.submit_onchain_intent(
        intent_commitment=intent_commitment,
        cluster=cluster_name,
    )
    mode = str(submission.get("metadata", {}).get("adapter_mode", adapter.bridge_mode))
    if require_real_submission and not SolanaAgentKitAdapter.is_real_submission_mode(mode):
        console.print(
            "[bold red]Submission did not use AgentKit session mode while real submission is required.[/bold red]"
        )
        raise typer.Exit(code=1)
    updated = store.update_arena_run_metadata(
        arena_run_id,
        {"onchain_submission": submission},
        actor_id=actor_id,
    )
    console.print(
        f"[bold green]Arena intent submitted:[/bold green] {updated.arena_run_id}\n"
        f"Status: {submission.get('submission_status')}\n"
        f"Signature: {submission.get('signature')}\n"
        f"Explorer: {submission.get('explorer_url')}"
    )


@app.command("arena-integrations")
def arena_integrations():
    """List Solana integration hub entries and local readiness."""
    rows = [integration_readiness(row) for row in load_solana_integrations()]
    table = Table(title="Solana Integration Hub")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Kind", style="yellow")
    table.add_column("Stage", style="magenta")
    table.add_column("Ready")
    table.add_column("Missing Tools")
    for row in rows:
        table.add_row(
            str(row["id"]),
            str(row["name"]),
            str(row["kind"]),
            str(row["status"]),
            "yes" if row["ready"] else "no",
            ", ".join(row["missing_tools"]) if row["missing_tools"] else "-",
        )
    console.print(table)


@app.command("mcp-serve")
def mcp_serve():
    """Start the OpenLVM MCP server."""
    serve_mcp()


if __name__ == "__main__":
    app()

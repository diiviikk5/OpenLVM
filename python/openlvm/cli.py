"""OpenLVM CLI powered by Typer and Rich."""

import json
import os
import shutil
import time
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
def doctor():
    """Inspect local OpenLVM readiness."""
    runtime = create_runtime()
    zig_installed = shutil.which("zig") is not None
    solana_installed = shutil.which("solana") is not None
    runtime_mode = os.getenv("OPENLVM_RUNTIME") or "auto"
    shared_lib = OpenLVMRuntime._default_library_path()

    table = Table(title="OpenLVM Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Detail", style="magenta")
    table.add_row("runtime backend", "ok", runtime.backend)
    table.add_row("runtime mode", "ok", runtime_mode)
    table.add_row("zig", "ok" if zig_installed else "missing", "installed" if zig_installed else "not on PATH")
    table.add_row(
        "solana cli",
        "ok" if solana_installed else "missing",
        "installed"
        if solana_installed
        else "run: curl -fsSL https://www.solana.new/setup.sh | bash",
    )
    table.add_row("shared library", "ok" if shared_lib.exists() else "missing", str(shared_lib))
    table.add_row("promptfoo adapter", "ok", "available" if PromptfooAdapter().available else "npx not found")
    table.add_row("deepeval adapter", "ok", "available" if DeepEvalAdapter().available else "fallback mode")
    table.add_row("openllmetry adapter", "ok", "available" if OpenLLMetryAdapter().available else "fallback mode")
    console.print(table)


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
    submit_intent: bool = typer.Option(False, "--submit-intent", help="Submit onchain intent immediately after run"),
    require_real_submission: bool = typer.Option(
        False,
        "--require-real-submission",
        help="Fail if onchain submission uses local stub mode",
    ),
    actor_id: str = typer.Option("arena-cli", "--actor-id", help="Actor id for audit trail"),
):
    """Run one Solana Arena scenario using the current local simulation engine."""
    if not scenario.exists():
        console.print(f"[bold red]Scenario file not found:[/bold red] {scenario}")
        raise typer.Exit(code=1)

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
        cluster=os.getenv("OPENLVM_SOLANA_CLUSTER", "devnet"),
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
        cluster = str(onchain_intent.get("cluster", "devnet") or "devnet")
        if not intent_commitment:
            console.print("[bold red]Intent commitment missing.[/bold red]")
            raise typer.Exit(code=1)
        submission = adapter.submit_onchain_intent(
            intent_commitment=intent_commitment,
            cluster=cluster,
        )
        mode = str(submission.get("metadata", {}).get("adapter_mode", adapter.bridge_mode))
        if require_real_submission and "stub" in mode:
            console.print("[bold red]Submission used stub mode while real submission is required.[/bold red]")
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
    require_real_submission: bool = typer.Option(
        False,
        "--require-real-submission",
        help="Fail if onchain submission uses local stub mode",
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
    cluster = str(intent.get("cluster", "devnet") or "devnet")
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
        cluster=cluster,
    )
    mode = str(submission.get("metadata", {}).get("adapter_mode", adapter.bridge_mode))
    if require_real_submission and "stub" in mode:
        console.print("[bold red]Submission used stub mode while real submission is required.[/bold red]")
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

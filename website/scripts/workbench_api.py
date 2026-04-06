"""Bridge script for Next.js API routes to interact with OpenLVM Python stores."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent.parent


def _bootstrap() -> None:
    repo_root = _repo_root()
    python_dir = repo_root / "python"
    if str(python_dir) not in sys.path:
        sys.path.insert(0, str(python_dir))


def _overview(args: list[str]) -> dict:
    from openlvm.eval_store import EvalStore
    from openlvm.operator_store import OperatorStore

    workspace_scope = args[0] if args else ""
    op_store = OperatorStore()
    eval_store = EvalStore()
    workspaces = [ws.model_dump() for ws in op_store.list_workspaces()]
    collections = [
        col.model_dump()
        for col in op_store.list_collections(workspace_scope or None)
    ]
    baselines_by_collection = {
        col["collection_id"]: [base.model_dump() for base in op_store.list_baselines(col["collection_id"])]
        for col in collections
    }
    scenarios_by_collection = {
        col["collection_id"]: [scn.model_dump() for scn in op_store.list_saved_scenarios(col["collection_id"])]
        for col in collections
    }
    recent_runs = [run.model_dump() for run in eval_store.list_runs(limit=20)]
    return {
        "workspaces": workspaces,
        "collections": collections,
        "baselines_by_collection": baselines_by_collection,
        "scenarios_by_collection": scenarios_by_collection,
        "recent_runs": recent_runs,
        "audit_events": op_store.list_audit_events(limit=100),
    }


def _run_collection(args: list[str]) -> dict:
    if not args:
        raise ValueError("collection_id is required")

    from openlvm.orchestrator import TestOrchestrator

    collection_id = args[0]
    scenarios = int(args[1]) if len(args) > 1 and args[1] else None
    chaos_mode = args[2] if len(args) > 2 and args[2] else None
    workspace_scope = args[3] if len(args) > 3 else ""
    if workspace_scope:
        _assert_collection_workspace(collection_id, workspace_scope)
    run = TestOrchestrator().run_collection(
        collection_id,
        scenarios=scenarios,
        chaos_mode=chaos_mode,
    )
    return run.model_dump()


def _run_details(args: list[str]) -> dict:
    from openlvm.eval_store import EvalStore

    run_id = args[0] if args else "latest"
    store = EvalStore()
    run = store.get_run(run_id).model_dump()
    trace_summary = store.get_trace_summary(run_id)
    return {"run": run, "trace_summary": trace_summary}


def _compare_baseline(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("collection_id and run_id are required")

    from openlvm.eval_store import EvalStore
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    run_id = args[1]
    baseline_id_csv = args[2] if len(args) > 2 else ""
    workspace_scope = args[3] if len(args) > 3 else ""
    if workspace_scope:
        _assert_collection_workspace(collection_id, workspace_scope)
    op_store = OperatorStore()
    baselines = op_store.list_baselines(collection_id)
    if not baselines:
        raise ValueError(f"No baselines found for collection: {collection_id}")

    selected_ids = {token for token in baseline_id_csv.split(",") if token}
    selected_baselines = [b for b in baselines if not selected_ids or b.baseline_id in selected_ids]
    if not selected_baselines:
        raise ValueError("No matching baselines for requested baseline_ids")

    eval_store = EvalStore()
    diffs = []
    for baseline in selected_baselines:
        diff = eval_store.compare_runs(baseline.run_id, run_id).model_dump()
        diff["baseline_id"] = baseline.baseline_id
        diff["baseline_label"] = baseline.label
        diffs.append(diff)
    return {"diffs": diffs, "candidate_run_id": run_id}


def _resolve_config_path(config_path: str) -> str:
    path = Path(config_path)
    if path.is_absolute():
        return str(path)
    return str((_repo_root() / path).resolve())


def _assert_collection_workspace(collection_id: str, workspace_id: str) -> None:
    from openlvm.operator_store import OperatorStore

    summary = OperatorStore().get_collection_summary(collection_id)
    actual_workspace = summary["workspace"]["workspace_id"]
    if actual_workspace != workspace_id:
        raise PermissionError(
            f"collection {collection_id} is not in workspace scope {workspace_id}"
        )


def _create_workspace(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("workspace name and actor_id are required")
    from openlvm.operator_store import OperatorStore

    name = args[0]
    actor_id = args[1]
    description = args[2] if len(args) > 2 else ""
    return OperatorStore().create_workspace(name, description, actor_id=actor_id).model_dump()


def _update_workspace(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("workspace_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    workspace_id = args[0]
    actor_id = args[1]
    name = args[2] if len(args) > 2 and args[2] else None
    description = args[3] if len(args) > 3 and args[3] else None
    return OperatorStore().update_workspace(
        workspace_id,
        name=name,
        description=description,
        actor_id=actor_id,
    ).model_dump()


def _delete_workspace(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("workspace_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    workspace_id = args[0]
    actor_id = args[1]
    deleted = OperatorStore().delete_workspace(workspace_id, actor_id=actor_id)
    return {"deleted": deleted}


def _create_collection(args: list[str]) -> dict:
    if len(args) < 3:
        raise ValueError("workspace_id, collection name, and actor_id are required")
    from openlvm.operator_store import OperatorStore

    workspace_id = args[0]
    name = args[1]
    actor_id = args[2]
    description = args[3] if len(args) > 3 else ""
    return OperatorStore().create_collection(workspace_id, name, description, actor_id=actor_id).model_dump()


def _update_collection(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("collection_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    actor_id = args[1]
    name = args[2] if len(args) > 2 and args[2] else None
    description = args[3] if len(args) > 3 and args[3] else None
    return OperatorStore().update_collection(
        collection_id,
        name=name,
        description=description,
        actor_id=actor_id,
    ).model_dump()


def _delete_collection(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("collection_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    actor_id = args[1]
    deleted = OperatorStore().delete_collection(collection_id, actor_id=actor_id)
    return {"deleted": deleted}


def _save_scenario(args: list[str]) -> dict:
    if len(args) < 5:
        raise ValueError("collection_id, name, config_path, input_text, actor_id are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    name = args[1]
    config_path = _resolve_config_path(args[2])
    input_text = args[3]
    actor_id = args[4]
    return OperatorStore().save_scenario(
        collection_id,
        name,
        config_path,
        input_text,
        actor_id=actor_id,
    ).model_dump()


def _save_baseline(args: list[str]) -> dict:
    if len(args) < 4:
        raise ValueError("collection_id, run_id, label, actor_id are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    run_id = args[1]
    label = args[2]
    actor_id = args[3]
    return OperatorStore().create_baseline(collection_id, run_id, label, actor_id=actor_id).model_dump()


def _list_scenarios(args: list[str]) -> dict:
    if not args:
        raise ValueError("collection_id is required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    rows = OperatorStore().list_saved_scenarios(collection_id)
    return {"scenarios": [row.model_dump() for row in rows]}


def _update_scenario(args: list[str]) -> dict:
    if len(args) < 5:
        raise ValueError("scenario_id, name, config_path, input_text, actor_id are required")
    from openlvm.operator_store import OperatorStore

    scenario_id = args[0]
    name = args[1]
    config_path = _resolve_config_path(args[2])
    input_text = args[3]
    actor_id = args[4]
    return OperatorStore().update_saved_scenario(
        scenario_id,
        name=name,
        config_path=config_path,
        input_text=input_text,
        actor_id=actor_id,
    ).model_dump()


def _delete_scenario(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("scenario_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    deleted = OperatorStore().delete_saved_scenario(args[0], actor_id=args[1])
    return {"deleted": deleted}


def _main() -> int:
    _bootstrap()
    if len(sys.argv) < 2:
        print(json.dumps({"error": "command required"}))
        return 1

    command = sys.argv[1]
    args = sys.argv[2:]

    try:
        if command == "overview":
            result = _overview(args)
        elif command == "run_collection":
            result = _run_collection(args)
        elif command == "run_details":
            result = _run_details(args)
        elif command == "compare_baseline":
            result = _compare_baseline(args)
        elif command == "create_workspace":
            result = _create_workspace(args)
        elif command == "update_workspace":
            result = _update_workspace(args)
        elif command == "delete_workspace":
            result = _delete_workspace(args)
        elif command == "create_collection":
            result = _create_collection(args)
        elif command == "update_collection":
            result = _update_collection(args)
        elif command == "delete_collection":
            result = _delete_collection(args)
        elif command == "save_scenario":
            result = _save_scenario(args)
        elif command == "save_baseline":
            result = _save_baseline(args)
        elif command == "list_scenarios":
            result = _list_scenarios(args)
        elif command == "update_scenario":
            result = _update_scenario(args)
        elif command == "delete_scenario":
            result = _delete_scenario(args)
        else:
            raise ValueError(f"unknown command: {command}")
        print(json.dumps(result))
        return 0
    except Exception as exc:  # pragma: no cover - bridge safety
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())

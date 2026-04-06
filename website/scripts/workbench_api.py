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


def _overview() -> dict:
    from openlvm.eval_store import EvalStore
    from openlvm.operator_store import OperatorStore

    op_store = OperatorStore()
    eval_store = EvalStore()
    workspaces = [ws.model_dump() for ws in op_store.list_workspaces()]
    collections = [col.model_dump() for col in op_store.list_collections()]
    baselines_by_collection = {
        col["collection_id"]: [base.model_dump() for base in op_store.list_baselines(col["collection_id"])]
        for col in collections
    }
    recent_runs = [run.model_dump() for run in eval_store.list_runs(limit=20)]
    return {
        "workspaces": workspaces,
        "collections": collections,
        "baselines_by_collection": baselines_by_collection,
        "recent_runs": recent_runs,
    }


def _run_collection(args: list[str]) -> dict:
    if not args:
        raise ValueError("collection_id is required")

    from openlvm.orchestrator import TestOrchestrator

    collection_id = args[0]
    scenarios = int(args[1]) if len(args) > 1 and args[1] else None
    chaos_mode = args[2] if len(args) > 2 and args[2] else None
    run = TestOrchestrator().run_collection(
        collection_id,
        scenarios=scenarios,
        chaos_mode=chaos_mode,
    )
    return run.model_dump()


def _compare_baseline(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("collection_id and run_id are required")

    from openlvm.eval_store import EvalStore
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    run_id = args[1]
    op_store = OperatorStore()
    baselines = op_store.list_baselines(collection_id)
    if not baselines:
        raise ValueError(f"No baselines found for collection: {collection_id}")
    diff = EvalStore().compare_runs(baselines[0].run_id, run_id)
    return diff.model_dump()


def _resolve_config_path(config_path: str) -> str:
    path = Path(config_path)
    if path.is_absolute():
        return str(path)
    return str((_repo_root() / path).resolve())


def _create_workspace(args: list[str]) -> dict:
    if not args:
        raise ValueError("workspace name is required")
    from openlvm.operator_store import OperatorStore

    name = args[0]
    description = args[1] if len(args) > 1 else ""
    return OperatorStore().create_workspace(name, description).model_dump()


def _create_collection(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("workspace_id and collection name are required")
    from openlvm.operator_store import OperatorStore

    workspace_id = args[0]
    name = args[1]
    description = args[2] if len(args) > 2 else ""
    return OperatorStore().create_collection(workspace_id, name, description).model_dump()


def _save_scenario(args: list[str]) -> dict:
    if len(args) < 4:
        raise ValueError("collection_id, name, config_path, input_text are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    name = args[1]
    config_path = _resolve_config_path(args[2])
    input_text = args[3]
    return OperatorStore().save_scenario(collection_id, name, config_path, input_text).model_dump()


def _save_baseline(args: list[str]) -> dict:
    if len(args) < 3:
        raise ValueError("collection_id, run_id, label are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    run_id = args[1]
    label = args[2]
    return OperatorStore().create_baseline(collection_id, run_id, label).model_dump()


def _main() -> int:
    _bootstrap()
    if len(sys.argv) < 2:
        print(json.dumps({"error": "command required"}))
        return 1

    command = sys.argv[1]
    args = sys.argv[2:]

    try:
        if command == "overview":
            result = _overview()
        elif command == "run_collection":
            result = _run_collection(args)
        elif command == "compare_baseline":
            result = _compare_baseline(args)
        elif command == "create_workspace":
            result = _create_workspace(args)
        elif command == "create_collection":
            result = _create_collection(args)
        elif command == "save_scenario":
            result = _save_scenario(args)
        elif command == "save_baseline":
            result = _save_baseline(args)
        else:
            raise ValueError(f"unknown command: {command}")
        print(json.dumps(result))
        return 0
    except Exception as exc:  # pragma: no cover - bridge safety
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())

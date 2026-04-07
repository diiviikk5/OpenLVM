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


def _actor_user_id(actor_id: str) -> str:
    token = (actor_id or "").strip()
    if not token:
        return "anonymous"
    return token.split("#", 1)[0] or "anonymous"


def _assert_workspace_access(workspace_id: str, actor_id: str, min_role: str) -> str:
    from openlvm.operator_store import OperatorStore

    user_id = _actor_user_id(actor_id)
    return OperatorStore().ensure_workspace_access(workspace_id, user_id, min_role=min_role)


def _require_authenticated_actor(actor_id: str) -> str:
    user_id = _actor_user_id(actor_id)
    if user_id == "anonymous":
        raise PermissionError("authenticated session required")
    return user_id


def _assert_collection_access(collection_id: str, actor_id: str, min_role: str) -> str:
    from openlvm.operator_store import OperatorStore

    summary = OperatorStore().get_collection_summary(collection_id)
    workspace_id = summary["workspace"]["workspace_id"]
    return _assert_workspace_access(workspace_id, actor_id, min_role)


def _workspace_accessible(store, workspace_id: str, user_id: str) -> bool:
    if user_id == "anonymous":
        return True
    try:
        store.ensure_workspace_access(workspace_id, user_id, min_role="viewer")
        return True
    except PermissionError:
        return False


def _overview(args: list[str]) -> dict:
    from openlvm.eval_store import EvalStore
    from openlvm.operator_store import OperatorStore

    workspace_scope = args[0] if args else ""
    actor_id = args[1] if len(args) > 1 else "system"
    user_id = _actor_user_id(actor_id)
    op_store = OperatorStore()
    eval_store = EvalStore()
    workspaces = [
        ws.model_dump()
        for ws in op_store.list_workspaces(user_id if user_id != "anonymous" else None)
    ]
    collections = [
        col.model_dump()
        for col in op_store.list_collections(workspace_scope or None)
        if (
            user_id == "anonymous"
            or _workspace_accessible(op_store, col.workspace_id, user_id)
        )
    ]
    baselines_by_collection = {
        col["collection_id"]: [base.model_dump() for base in op_store.list_baselines(col["collection_id"])]
        for col in collections
    }
    scenarios_by_collection = {
        col["collection_id"]: [scn.model_dump() for scn in op_store.list_saved_scenarios(col["collection_id"])]
        for col in collections
    }
    compare_artifacts_by_collection = {
        col["collection_id"]: [
            {
                "artifact_id": art.artifact_id,
                "collection_id": art.collection_id,
                "candidate_run_id": art.candidate_run_id,
                "baseline_ids": art.baseline_ids,
                "filename": art.filename,
                "created_at": art.created_at,
                "actor_id": art.actor_id,
            }
            for art in op_store.list_compare_artifacts(col["collection_id"], limit=20)
        ]
        for col in collections
    }
    recent_runs = [run.model_dump() for run in eval_store.list_runs(limit=20)]
    members_by_workspace = {
        ws["workspace_id"]: [m.model_dump() for m in op_store.list_workspace_members(ws["workspace_id"])]
        for ws in workspaces
    }
    user_role_by_workspace = {
        ws["workspace_id"]: (op_store.get_workspace_member_role(ws["workspace_id"], user_id) or "")
        for ws in workspaces
    }
    return {
        "workspaces": workspaces,
        "collections": collections,
        "baselines_by_collection": baselines_by_collection,
        "scenarios_by_collection": scenarios_by_collection,
        "compare_artifacts_by_collection": compare_artifacts_by_collection,
        "members_by_workspace": members_by_workspace,
        "user_role_by_workspace": user_role_by_workspace,
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
    actor_id = args[4] if len(args) > 4 else "system"
    _require_authenticated_actor(actor_id)
    _assert_collection_access(collection_id, actor_id, "editor")
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


def _compute_compare_payload(
    collection_id: str,
    run_id: str,
    baseline_id_csv: str,
    workspace_scope: str,
    actor_id: str,
) -> tuple[dict, list[str]]:
    from openlvm.eval_store import EvalStore
    from openlvm.operator_store import OperatorStore

    _assert_collection_access(collection_id, actor_id, "viewer")
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
    return {"diffs": diffs, "candidate_run_id": run_id}, [b.baseline_id for b in selected_baselines]


def _compare_baseline(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("collection_id and run_id are required")

    collection_id = args[0]
    run_id = args[1]
    baseline_id_csv = args[2] if len(args) > 2 else ""
    workspace_scope = args[3] if len(args) > 3 else ""
    actor_id = args[4] if len(args) > 4 else "system"
    payload, _ = _compute_compare_payload(collection_id, run_id, baseline_id_csv, workspace_scope, actor_id)
    return payload


def _save_compare_artifact(args: list[str]) -> dict:
    if len(args) < 4:
        raise ValueError("collection_id, run_id, baseline_ids, and actor_id are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    run_id = args[1]
    baseline_id_csv = args[2] if len(args) > 2 else ""
    actor_id = args[3]
    workspace_scope = args[4] if len(args) > 4 else ""
    _require_authenticated_actor(actor_id)
    _assert_collection_access(collection_id, actor_id, "editor")
    payload, baseline_ids = _compute_compare_payload(
        collection_id, run_id, baseline_id_csv, workspace_scope, actor_id
    )
    artifact = OperatorStore().save_compare_artifact(
        collection_id,
        run_id,
        baseline_ids,
        payload,
        actor_id=actor_id,
    )
    return {
        "artifact_id": artifact.artifact_id,
        "filename": artifact.filename,
        "created_at": artifact.created_at,
        "candidate_run_id": artifact.candidate_run_id,
        "baseline_ids": artifact.baseline_ids,
    }


def _list_compare_artifacts(args: list[str]) -> dict:
    if not args:
        raise ValueError("collection_id is required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    workspace_scope = args[1] if len(args) > 1 else ""
    actor_id = args[2] if len(args) > 2 else "system"
    _assert_collection_access(collection_id, actor_id, "viewer")
    if workspace_scope:
        _assert_collection_workspace(collection_id, workspace_scope)
    rows = OperatorStore().list_compare_artifacts(collection_id, limit=50)
    return {
        "artifacts": [
            {
                "artifact_id": row.artifact_id,
                "collection_id": row.collection_id,
                "candidate_run_id": row.candidate_run_id,
                "baseline_ids": row.baseline_ids,
                "filename": row.filename,
                "created_at": row.created_at,
                "actor_id": row.actor_id,
            }
            for row in rows
        ]
    }


def _download_compare_artifact(args: list[str]) -> dict:
    if not args:
        raise ValueError("artifact_id is required")
    from openlvm.operator_store import OperatorStore

    artifact_id = args[0]
    output_format = args[1] if len(args) > 1 else "json"
    workspace_scope = args[2] if len(args) > 2 else ""
    actor_id = args[3] if len(args) > 3 else "system"
    artifact = OperatorStore().get_compare_artifact(artifact_id)
    _assert_collection_access(artifact.collection_id, actor_id, "viewer")
    if workspace_scope:
        _assert_collection_workspace(artifact.collection_id, workspace_scope)
    if output_format == "json":
        content = json.dumps(artifact.payload, indent=2)
        mime_type = "application/json"
        extension = "json"
    elif output_format == "csv":
        content = _compare_payload_to_csv(artifact.payload)
        mime_type = "text/csv"
        extension = "csv"
    else:
        raise ValueError("format must be json or csv")
    filename_base = artifact.filename.rsplit(".", 1)[0]
    return {
        "artifact_id": artifact.artifact_id,
        "collection_id": artifact.collection_id,
        "candidate_run_id": artifact.candidate_run_id,
        "baseline_ids": artifact.baseline_ids,
        "filename": f"{filename_base}.{extension}",
        "mime_type": mime_type,
        "content": content,
        "created_at": artifact.created_at,
    }


def _delete_compare_artifact(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("artifact_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    artifact_id = args[0]
    actor_id = args[1]
    workspace_scope = args[2] if len(args) > 2 else ""
    _require_authenticated_actor(actor_id)
    store = OperatorStore()
    artifact = store.get_compare_artifact(artifact_id)
    _assert_collection_access(artifact.collection_id, actor_id, "editor")
    if workspace_scope:
        _assert_collection_workspace(artifact.collection_id, workspace_scope)
    deleted = store.delete_compare_artifact(artifact_id, actor_id=actor_id)
    return {"deleted": deleted, "artifact_id": artifact_id}


def _delete_compare_artifacts_bulk(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("artifact_ids_csv and actor_id are required")
    from openlvm.operator_store import OperatorStore

    artifact_ids = [token for token in args[0].split(",") if token]
    actor_id = args[1]
    workspace_scope = args[2] if len(args) > 2 else ""
    _require_authenticated_actor(actor_id)
    store = OperatorStore()
    for artifact_id in artifact_ids:
        artifact = store.get_compare_artifact(artifact_id)
        _assert_collection_access(artifact.collection_id, actor_id, "editor")
        if workspace_scope:
            _assert_collection_workspace(artifact.collection_id, workspace_scope)
    deleted_count = store.delete_compare_artifacts_bulk(artifact_ids, actor_id=actor_id)
    return {"deleted_count": deleted_count, "artifact_ids": artifact_ids}


def _prune_compare_artifacts(args: list[str]) -> dict:
    if len(args) < 3:
        raise ValueError("collection_id, keep_latest, and actor_id are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    keep_latest = int(args[1])
    actor_id = args[2]
    workspace_scope = args[3] if len(args) > 3 else ""
    _require_authenticated_actor(actor_id)
    _assert_collection_access(collection_id, actor_id, "editor")
    if workspace_scope:
        _assert_collection_workspace(collection_id, workspace_scope)
    deleted_count = OperatorStore().prune_compare_artifacts(
        collection_id,
        keep_latest,
        actor_id=actor_id,
    )
    return {"collection_id": collection_id, "deleted_count": deleted_count, "keep_latest": keep_latest}


def _compare_payload_to_csv(payload: dict) -> str:
    header = [
        "baseline_id",
        "baseline_label",
        "baseline_run_id",
        "candidate_run_id",
        "scenario_name",
        "baseline_status",
        "candidate_status",
        "baseline_score",
        "candidate_score",
        "warning_delta",
        "trace_count_delta",
        "warning_event_delta",
    ]
    lines = [",".join(f'"{field}"' for field in header)]
    diffs = payload.get("diffs", [])
    for diff in diffs:
        for scenario in diff.get("scenario_diffs", []):
            row = [
                diff.get("baseline_id", ""),
                diff.get("baseline_label", ""),
                diff.get("baseline_run_id", ""),
                diff.get("candidate_run_id", ""),
                scenario.get("name", ""),
                scenario.get("baseline_status", ""),
                scenario.get("candidate_status", ""),
                scenario.get("baseline_score", ""),
                scenario.get("candidate_score", ""),
                scenario.get("warning_delta", ""),
                diff.get("trace_delta", {}).get("trace_count_delta", ""),
                diff.get("trace_delta", {}).get("warning_event_delta", ""),
            ]
            escaped = ['"' + str(value).replace('"', '""') + '"' for value in row]
            lines.append(",".join(escaped))
    return "\n".join(lines)


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
    _require_authenticated_actor(actor_id)
    return OperatorStore().create_workspace(name, description, actor_id=actor_id).model_dump()


def _update_workspace(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("workspace_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    workspace_id = args[0]
    actor_id = args[1]
    name = args[2] if len(args) > 2 and args[2] else None
    description = args[3] if len(args) > 3 and args[3] else None
    _require_authenticated_actor(actor_id)
    _assert_workspace_access(workspace_id, actor_id, "admin")
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
    _require_authenticated_actor(actor_id)
    _assert_workspace_access(workspace_id, actor_id, "owner")
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
    _require_authenticated_actor(actor_id)
    _assert_workspace_access(workspace_id, actor_id, "editor")
    return OperatorStore().create_collection(workspace_id, name, description, actor_id=actor_id).model_dump()


def _update_collection(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("collection_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    actor_id = args[1]
    name = args[2] if len(args) > 2 and args[2] else None
    description = args[3] if len(args) > 3 and args[3] else None
    _require_authenticated_actor(actor_id)
    _assert_collection_access(collection_id, actor_id, "editor")
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
    _require_authenticated_actor(actor_id)
    _assert_collection_access(collection_id, actor_id, "admin")
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
    _require_authenticated_actor(actor_id)
    _assert_collection_access(collection_id, actor_id, "editor")
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
    _require_authenticated_actor(actor_id)
    _assert_collection_access(collection_id, actor_id, "editor")
    return OperatorStore().create_baseline(collection_id, run_id, label, actor_id=actor_id).model_dump()


def _list_scenarios(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("collection_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    collection_id = args[0]
    actor_id = args[1]
    _assert_collection_access(collection_id, actor_id, "viewer")
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
    _require_authenticated_actor(actor_id)
    scenario = OperatorStore().get_saved_scenario(scenario_id)
    _assert_collection_access(scenario.collection_id, actor_id, "editor")
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

    store = OperatorStore()
    _require_authenticated_actor(args[1])
    scenario = store.get_saved_scenario(args[0])
    _assert_collection_access(scenario.collection_id, args[1], "editor")
    deleted = store.delete_saved_scenario(args[0], actor_id=args[1])
    return {"deleted": deleted}


def _list_workspace_members(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("workspace_id and actor_id are required")
    from openlvm.operator_store import OperatorStore

    workspace_id = args[0]
    actor_id = args[1]
    _require_authenticated_actor(actor_id)
    _assert_workspace_access(workspace_id, actor_id, "viewer")
    members = OperatorStore().list_workspace_members(workspace_id)
    return {"members": [member.model_dump() for member in members]}


def _upsert_workspace_member(args: list[str]) -> dict:
    if len(args) < 4:
        raise ValueError("workspace_id, user_id, role, and actor_id are required")
    from openlvm.operator_store import OperatorStore

    workspace_id = args[0]
    user_id = args[1]
    role = args[2]
    actor_id = args[3]
    _require_authenticated_actor(actor_id)
    _assert_workspace_access(workspace_id, actor_id, "admin")
    member = OperatorStore().upsert_workspace_member(
        workspace_id,
        user_id,
        role,
        actor_id=actor_id,
    )
    return member.model_dump()


def _remove_workspace_member(args: list[str]) -> dict:
    if len(args) < 3:
        raise ValueError("workspace_id, user_id, and actor_id are required")
    from openlvm.operator_store import OperatorStore

    workspace_id = args[0]
    user_id = args[1]
    actor_id = args[2]
    _require_authenticated_actor(actor_id)
    _assert_workspace_access(workspace_id, actor_id, "admin")
    deleted = OperatorStore().remove_workspace_member(workspace_id, user_id, actor_id=actor_id)
    return {"deleted": deleted, "workspace_id": workspace_id, "user_id": user_id}


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
        elif command == "save_compare_artifact":
            result = _save_compare_artifact(args)
        elif command == "list_compare_artifacts":
            result = _list_compare_artifacts(args)
        elif command == "download_compare_artifact":
            result = _download_compare_artifact(args)
        elif command == "delete_compare_artifact":
            result = _delete_compare_artifact(args)
        elif command == "delete_compare_artifacts_bulk":
            result = _delete_compare_artifacts_bulk(args)
        elif command == "prune_compare_artifacts":
            result = _prune_compare_artifacts(args)
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
        elif command == "list_workspace_members":
            result = _list_workspace_members(args)
        elif command == "upsert_workspace_member":
            result = _upsert_workspace_member(args)
        elif command == "remove_workspace_member":
            result = _remove_workspace_member(args)
        else:
            raise ValueError(f"unknown command: {command}")
        print(json.dumps(result))
        return 0
    except Exception as exc:  # pragma: no cover - bridge safety
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())

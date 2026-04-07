from openlvm.operator_store import OperatorStore


def test_operator_store_creates_workspace_collection_scenario_and_baseline(tmp_path):
    store = OperatorStore(tmp_path / "operator_store.db")
    workspace = store.create_workspace("Team A", "Primary workspace")
    collection = store.create_collection(workspace.workspace_id, "Customer Support")
    scenario = store.save_scenario(
        collection.collection_id,
        "cancel-flow",
        "examples/swarm.yaml",
        "Help me cancel my subscription",
    )
    baseline = store.create_baseline(collection.collection_id, "run-123", "stable")

    assert store.list_workspaces()[0].workspace_id == workspace.workspace_id
    assert store.list_collections(workspace.workspace_id)[0].collection_id == collection.collection_id
    assert store.list_saved_scenarios(collection.collection_id)[0].scenario_id == scenario.scenario_id
    assert store.list_baselines(collection.collection_id)[0].baseline_id == baseline.baseline_id


def test_operator_store_updates_deletes_and_audits(tmp_path):
    store = OperatorStore(tmp_path / "operator_store.db")
    workspace = store.create_workspace("Team A", actor_id="alice")
    collection = store.create_collection(workspace.workspace_id, "Customer Support", actor_id="alice")

    updated_workspace = store.update_workspace(workspace.workspace_id, name="Team Alpha", actor_id="bob")
    updated_collection = store.update_collection(collection.collection_id, name="Support Ops", actor_id="bob")
    assert updated_workspace.name == "Team Alpha"
    assert updated_collection.name == "Support Ops"

    assert store.delete_collection(collection.collection_id, actor_id="carol") is True
    assert store.delete_workspace(workspace.workspace_id, actor_id="carol") is True

    actions = [event["action"] for event in store.list_audit_events(limit=20)]
    assert "workspace.create" in actions
    assert "workspace.update" in actions
    assert "collection.create" in actions
    assert "collection.update" in actions
    assert "collection.delete" in actions
    assert "workspace.delete" in actions


def test_operator_store_compare_artifacts(tmp_path):
    store = OperatorStore(tmp_path / "operator_store.db")
    workspace = store.create_workspace("Team A", actor_id="alice")
    collection = store.create_collection(workspace.workspace_id, "Customer Support", actor_id="alice")
    payload = {
        "candidate_run_id": "run-222",
        "diffs": [
            {
                "baseline_id": "base-1",
                "baseline_run_id": "run-111",
                "candidate_run_id": "run-222",
                "scenario_diffs": [],
            }
        ],
    }

    artifact = store.save_compare_artifact(
        collection.collection_id,
        "run-222",
        ["base-1"],
        payload,
        actor_id="alice",
    )
    listed = store.list_compare_artifacts(collection.collection_id)
    fetched = store.get_compare_artifact(artifact.artifact_id)

    assert listed[0].artifact_id == artifact.artifact_id
    assert fetched.candidate_run_id == "run-222"
    assert fetched.baseline_ids == ["base-1"]
    assert fetched.payload["candidate_run_id"] == "run-222"
    artifact_2 = store.save_compare_artifact(
        collection.collection_id,
        "run-333",
        ["base-2"],
        payload,
        actor_id="alice",
    )
    artifact_3 = store.save_compare_artifact(
        collection.collection_id,
        "run-444",
        ["base-3"],
        payload,
        actor_id="alice",
    )
    deleted = store.delete_compare_artifact(artifact.artifact_id, actor_id="alice")
    assert deleted is True
    bulk_deleted = store.delete_compare_artifacts_bulk(
        [artifact_2.artifact_id, artifact_3.artifact_id],
        actor_id="alice",
    )
    assert bulk_deleted == 2
    pruned_count = store.prune_compare_artifacts(collection.collection_id, keep_latest=0, actor_id="alice")
    assert pruned_count >= 0
    actions = [event["action"] for event in store.list_audit_events(limit=50)]
    assert "compare_artifact.create" in actions
    assert "compare_artifact.delete" in actions
    assert "compare_artifact.bulk_delete" in actions
    assert "compare_artifact.prune" in actions


def test_operator_store_workspace_members_and_roles(tmp_path):
    store = OperatorStore(tmp_path / "operator_store.db")
    workspace = store.create_workspace("Team A", actor_id="alice#s1")

    members = store.list_workspace_members(workspace.workspace_id)
    assert len(members) == 1
    assert members[0].user_id == "alice"
    assert members[0].role == "owner"

    store.upsert_workspace_member(workspace.workspace_id, "bob", "editor", actor_id="alice#s1")
    assert store.get_workspace_member_role(workspace.workspace_id, "bob") == "editor"
    store.ensure_workspace_access(workspace.workspace_id, "bob", min_role="viewer")
    store.ensure_workspace_access(workspace.workspace_id, "bob", min_role="editor")

    try:
        store.ensure_workspace_access(workspace.workspace_id, "bob", min_role="admin")
    except PermissionError:
        pass
    else:
        raise AssertionError("bob should not have admin access")

    removed = store.remove_workspace_member(workspace.workspace_id, "bob", actor_id="alice#s1")
    assert removed is True
    assert store.get_workspace_member_role(workspace.workspace_id, "bob") is None


def test_operator_store_legacy_workspace_stays_accessible(tmp_path):
    store = OperatorStore(tmp_path / "operator_store.db")
    workspace = store.create_workspace("Legacy", actor_id="system")

    assert store.list_workspace_members(workspace.workspace_id) == []
    store.ensure_workspace_access(workspace.workspace_id, "anonymous", min_role="viewer")
    store.ensure_workspace_access(workspace.workspace_id, "random-user", min_role="admin")

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

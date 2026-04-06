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

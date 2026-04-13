from openlvm.solana_hub import integration_readiness, load_solana_integrations


def test_solana_hub_registry_loads():
    rows = load_solana_integrations()
    assert rows, "solana integration registry should not be empty"
    ids = {row.get("id") for row in rows}
    assert "agentkit" in ids
    assert "x402" in ids


def test_solana_hub_readiness_shape():
    row = {
        "id": "agentkit",
        "name": "Solana AgentKit",
        "kind": "agent-runtime",
        "required_tools": ["node"],
        "status": "mvp",
    }
    readiness = integration_readiness(row)
    assert readiness["id"] == "agentkit"
    assert isinstance(readiness["missing_tools"], list)
    assert isinstance(readiness["ready"], bool)

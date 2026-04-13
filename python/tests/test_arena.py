from openlvm.arena import build_onchain_intent, build_trace_commitment


def test_trace_commitment_is_deterministic():
    payload = {"b": 2, "a": 1}
    first = build_trace_commitment(payload)
    second = build_trace_commitment({"a": 1, "b": 2})
    assert first == second
    assert first.startswith("sha256:")


def test_onchain_intent_has_seed_bundle_and_commitment():
    trace_commitment = build_trace_commitment({"run_id": "run-1"})
    intent = build_onchain_intent(
        agent_address="Agent111",
        scenario_id="scenario-a",
        score=0.82,
        status="passed",
        payment={
            "amount_usdc": 0.07,
            "tx_ref": "x402-abc123",
        },
        trace_commitment=trace_commitment,
        cluster="devnet",
    )
    assert intent["schema"] == "openlvm.arena.intent.v1"
    assert intent["seed_bundle"]["scenario_id"] == "scenario-a"
    assert intent["seed_bundle"]["trace_commitment"] == trace_commitment
    assert intent["tx_intent"]["intent_type"] == "x402_settle_and_commit"
    assert intent["tx_intent"]["score_bps"] == 8200
    assert str(intent["intent_commitment"]).startswith("sha256:")
